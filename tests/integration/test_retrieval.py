"""Integration tests for PgVectorRetriever - real Postgres/pgvector, hand-constructed vectors
(no real embedding model - this tests the SQL/retrieval logic, not embedding quality).

Requires local Postgres/pgvector (`docker compose up postgres` in docker/) with migrations
applied (`alembic upgrade head`), same as tests/integration/test_storage.py.

Isolation: tests/integration/conftest.py's db_session wraps each test in a transaction that's
rolled back afterward, so nothing this file writes ever persists. That does NOT hide rows
already committed by something else before the test starts (pre-existing local dev data,
another test file's data, a parallel worker) - retriever.search() correctly searches the whole
table, unscoped, so every assertion here filters results down to this fixture's own
document_id before checking order/membership/score, and top_k is set to the current total row
count so this fixture's own chunks are never crowded out of the result window by unrelated data.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.config import settings
from knowledge_assistant.domain import RetrievedChunk
from knowledge_assistant.retrieval.pgvector import PgVectorRetriever
from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel

_DIM = settings.embedding_dimension


def _unit_vector(index: int) -> list[float]:
    """A one-hot vector along `index` - orthogonal to other axes, magnitude 1."""
    vector = [0.0] * _DIM
    vector[index] = 1.0
    return vector


def _halfway_vector(index_a: int, index_b: int) -> list[float]:
    """A unit vector at 45 degrees between axes `index_a` and `index_b` (cosine similarity
    ~0.7071 with either pure axis vector)."""
    vector = [0.0] * _DIM
    vector[index_a] = 1 / math.sqrt(2)
    vector[index_b] = 1 / math.sqrt(2)
    return vector


def _own_chunks(results: list[RetrievedChunk], document_id: uuid.UUID) -> list[RetrievedChunk]:
    """Narrows a (possibly noisy) result set down to this fixture's own chunks, preserving the
    order the retriever returned them in."""
    return [r for r in results if r.document_id == document_id]


async def _unbounded_top_k(session: AsyncSession) -> int:
    """A top_k guaranteed to be >= the current row count, so LIMIT never excludes this
    fixture's own chunks regardless of how much unrelated data is also in the table."""
    total = await session.scalar(select(func.count()).select_from(DocumentChunkModel))
    return total + 1


@pytest.fixture
async def seeded_document(db_session: AsyncSession) -> AsyncGenerator[DocumentModel]:
    """One document with three chunks: identical to the query axis (score ~1.0), halfway
    between it and an orthogonal axis (score ~0.7071), and fully orthogonal (score ~0.0)."""
    document = DocumentModel(
        id=uuid.uuid4(),
        name="retrieval-fixture.md",
        source="docs/retrieval-fixture.md",
        content_hash=f"hash-{uuid.uuid4()}",
    )
    document.chunks.extend(
        [
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=0,
                content="identical to query",
                embedding=_unit_vector(0),
            ),
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=1,
                content="halfway between query and orthogonal",
                embedding=_halfway_vector(0, 1),
            ),
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=2,
                content="orthogonal to query",
                embedding=_unit_vector(1),
            ),
        ]
    )
    db_session.add(document)
    await db_session.commit()
    yield document


@pytest.mark.integration
async def test_results_ordered_by_similarity_closest_first(
    db_session: AsyncSession, seeded_document: DocumentModel
) -> None:
    retriever = PgVectorRetriever(db_session)
    top_k = await _unbounded_top_k(db_session)

    results = await retriever.search(query_embedding=_unit_vector(0), top_k=top_k)
    own = _own_chunks(results, seeded_document.id)

    assert [r.chunk_index for r in own] == [0, 1, 2]
    assert own[0].score > own[1].score > own[2].score


@pytest.mark.integration
async def test_identical_vector_scores_at_or_near_one(
    db_session: AsyncSession, seeded_document: DocumentModel
) -> None:
    retriever = PgVectorRetriever(db_session)
    top_k = await _unbounded_top_k(db_session)

    results = await retriever.search(query_embedding=_unit_vector(0), top_k=top_k)
    own = _own_chunks(results, seeded_document.id)

    identical = next(r for r in own if r.chunk_index == 0)
    assert identical.score == pytest.approx(1.0, abs=1e-6)


@pytest.mark.integration
async def test_orthogonal_vector_scores_at_or_near_zero(
    db_session: AsyncSession, seeded_document: DocumentModel
) -> None:
    retriever = PgVectorRetriever(db_session)
    top_k = await _unbounded_top_k(db_session)

    results = await retriever.search(query_embedding=_unit_vector(0), top_k=top_k)
    own = _own_chunks(results, seeded_document.id)

    orthogonal = next(r for r in own if r.chunk_index == 2)
    assert orthogonal.score == pytest.approx(0.0, abs=1e-6)


@pytest.mark.integration
async def test_document_and_chunk_metadata_populated(
    db_session: AsyncSession, seeded_document: DocumentModel
) -> None:
    retriever = PgVectorRetriever(db_session)
    top_k = await _unbounded_top_k(db_session)

    results = await retriever.search(query_embedding=_unit_vector(0), top_k=top_k)
    own = _own_chunks(results, seeded_document.id)

    top = next(r for r in own if r.chunk_index == 0)
    assert top.document_id == seeded_document.id
    assert top.document_name == "retrieval-fixture.md"
    assert top.chunk_index == 0
    assert top.content == "identical to query"


@pytest.mark.integration
async def test_top_k_limits_result_count(
    db_session: AsyncSession, seeded_document: DocumentModel
) -> None:
    # Data-agnostic: LIMIT caps the total row count regardless of what else is in the table,
    # so this doesn't need the _own_chunks/_unbounded_top_k treatment the other tests use.
    retriever = PgVectorRetriever(db_session)

    results = await retriever.search(query_embedding=_unit_vector(0), top_k=2)

    assert len(results) == 2


@pytest.mark.integration
async def test_similarity_threshold_excludes_chunks_below_it(
    db_session: AsyncSession, seeded_document: DocumentModel
) -> None:
    retriever = PgVectorRetriever(db_session)
    top_k = await _unbounded_top_k(db_session)

    results = await retriever.search(
        query_embedding=_unit_vector(0), top_k=top_k, similarity_threshold=0.5
    )
    own = _own_chunks(results, seeded_document.id)

    assert {r.chunk_index for r in own} == {0, 1}
    assert all(r.score >= 0.5 for r in own)
