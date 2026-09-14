"""End-to-end integration test for the ingestion flow: parse -> chunk -> embed -> persist as
Document + DocumentChunk rows, then a capstone check that the ingested chunks are actually
retrievable via PgVectorRetriever.

No fakes here - real parser, real chunker, real embedding model, real Postgres/pgvector, same
"prove it actually works together" philosophy as the real end-to-end query test.

The inline `_ingest` helper this file used to define is gone - it's now the shared
`ingestion.service.ingest_document`, also used by evaluation/runner.py and seed/seed.py. Most
tests below were a clean win to refactor onto it. One test
(test_reingesting_same_content_violates_content_hash_uniqueness) deliberately still bypasses
ingest_document: it exists to prove the raw DB constraint itself rejects a duplicate
content_hash, independent of ingest_document's own idempotency check - since ingest_document
now checks-then-skips *before* attempting an insert, calling it twice would never reach the
constraint at all, silently making that test meaningless if switched over. See that test's own
docstring for the full reasoning.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.config import settings
from knowledge_assistant.dependencies import get_embedding_model
from knowledge_assistant.ingestion.parser import get_parser
from knowledge_assistant.ingestion.service import ingest_document
from knowledge_assistant.retrieval.pgvector import PgVectorRetriever
from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel

_FIXTURE_MARKDOWN = """\
# API Rate Limits

The default API rate limit is 100 requests per minute per API key. This applies to all
standard-tier accounts and is enforced at the gateway level, independent of which endpoint is
being called. Exceeding the limit returns an HTTP 429 response with a Retry-After header
indicating how many seconds to wait before retrying.

Enterprise plans can request an increase to 500 requests per minute by contacting support with
their account ID and expected peak traffic. Increases are typically applied within one business
day and do not require a service restart.

# Credential Rotation

Rotate production API credentials every 90 days via the admin console. Credentials that are not
rotated within 120 days of issuance are automatically revoked, and any service still using a
revoked credential will start receiving HTTP 401 responses immediately. Rotating a credential
does not require downtime - both the old and new credential remain valid for a 24-hour overlap
window so dependent services can be updated without an outage.
"""


@pytest.mark.integration
async def test_ingestion_flow_persists_document_and_chunks_with_real_embeddings(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    path = tmp_path / "rate-limits-and-auth.md"
    path.write_bytes(_FIXTURE_MARKDOWN.encode("utf-8"))
    expected_content_hash = get_parser(path).parse(path).content_hash

    document = await ingest_document(path, db_session, get_embedding_model())
    assert document is not None

    assert document.content_hash == expected_content_hash

    # Verify the actual persisted rows, not just what ingest_document happened to return -
    # ingest_document's return type (domain.Document) doesn't carry chunks, by design (storage/
    # is a boundary; chunks are DocumentChunkModel rows, queried here directly).
    result = await db_session.execute(
        select(DocumentChunkModel)
        .where(DocumentChunkModel.document_id == document.id)
        .order_by(DocumentChunkModel.chunk_index)
    )
    chunks = result.scalars().all()

    assert len(chunks) >= 2, "fixture must be long enough to produce multiple chunks"
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == settings.embedding_dimension
        assert chunk.content.strip() != ""


@pytest.mark.integration
async def test_ingest_document_is_idempotent(tmp_path: Path, db_session: AsyncSession) -> None:
    """ingest_document's own idempotency check (not the DB constraint, not
    ingest_directory's directory-level skip - see this file's module docstring and
    test_reingesting_same_content_violates_content_hash_uniqueness below): calling it twice
    with byte-identical content returns the same document the first time, and None (a clean
    skip, no error) the second."""
    path = tmp_path / "rate-limits-and-auth.md"
    path.write_bytes(_FIXTURE_MARKDOWN.encode("utf-8"))

    first = await ingest_document(path, db_session, get_embedding_model())
    second = await ingest_document(path, db_session, get_embedding_model())

    assert first is not None
    assert second is None


@pytest.mark.integration
async def test_ingested_chunks_are_retrievable_via_pgvector_retriever(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    """Capstone check: proves the ingest -> retrieve loop actually works end-to-end, not just
    that rows got written."""
    path = tmp_path / "rate-limits-and-auth.md"
    path.write_bytes(_FIXTURE_MARKDOWN.encode("utf-8"))

    embedder = get_embedding_model()
    document = await ingest_document(path, db_session, embedder)
    assert document is not None

    query_embedding = (await embedder.embed(["What is the API rate limit?"]))[0]

    retriever = PgVectorRetriever(db_session)
    results = await retriever.search(query_embedding, top_k=3)

    assert any(r.document_id == document.id for r in results)
    top = next(r for r in results if r.document_id == document.id)
    assert "rate limit" in top.content.lower()


@pytest.mark.integration
async def test_reingesting_same_content_violates_content_hash_uniqueness(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    """content_hash is the natural dedupe key for idempotent re-ingestion - this proves the
    unique constraint (uq_documents_content_hash) itself really does reject a second Document
    row with the same content_hash, rather than silently duplicating data.

    Deliberately does NOT use ingest_document here (unlike the other tests in this file):
    ingest_document checks for an existing content_hash and skips *before* ever attempting an
    insert, so calling it twice would just return None both times - the raw insert path (and
    therefore this constraint) would never be exercised, and this test would silently stop
    testing anything. Inserting directly via the ORM models is the correct way to test the
    schema-level guarantee that ingest_document's own idempotency check is itself relying on.
    """
    content_hash = "duplicate-content-hash-for-this-test"

    def _make_document() -> DocumentModel:
        document = DocumentModel(
            id=uuid.uuid4(),
            name="dup.md",
            source="dup.md",
            content_hash=content_hash,
        )
        document.chunks.append(
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=0,
                content="irrelevant for this test",
                embedding=[0.0] * settings.embedding_dimension,
            )
        )
        return document

    db_session.add(_make_document())
    await db_session.commit()

    db_session.add(_make_document())
    with pytest.raises(IntegrityError):
        await db_session.commit()

    # Required after a failed flush/commit so the outer test-isolation transaction (see
    # tests/integration/conftest.py) can still clean up normally.
    await db_session.rollback()
