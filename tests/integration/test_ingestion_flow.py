"""End-to-end integration test for the ingestion flow (docs/ARCHITECTURE.md section 3.1):
parse -> chunk -> embed -> persist as Document + DocumentChunk rows, then a capstone check that
the ingested chunks are actually retrievable via PgVectorRetriever.

No fakes here - real parser, real chunker, real embedding model, real Postgres/pgvector, same
"prove it actually works together" philosophy as Step 10 sub-step 5's real end-to-end query
test. There's no "ingestion service" module yet (that's Step 15) - this test composes the
existing pieces directly/inline; a small `_ingest` helper keeps the composition readable
without building production code that isn't in scope for this step.

Requires local Postgres/pgvector (`docker compose up postgres` in docker/) with migrations
applied (`alembic upgrade head`), same as the rest of tests/integration/.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.config import settings
from knowledge_assistant.dependencies import get_embedding_model
from knowledge_assistant.domain import ParsedDocument
from knowledge_assistant.ingestion.chunker import RecursiveCharacterChunker
from knowledge_assistant.ingestion.parser import get_parser
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


async def _ingest(path: Path, db_session: AsyncSession) -> DocumentModel:
    """Runs the real parse -> chunk -> embed -> persist flow inline (no ingestion-service
    module yet - that's Step 15) and returns the persisted Document (with chunks loaded)."""
    parsed: ParsedDocument = get_parser(path).parse(path)
    chunker = RecursiveCharacterChunker(settings.chunk_size, settings.chunk_overlap)
    chunk_texts = chunker.chunk(parsed.text)
    assert len(chunk_texts) >= 2, "fixture must be long enough to produce multiple chunks"

    embedder = get_embedding_model()
    embeddings = await embedder.embed(chunk_texts)

    document = DocumentModel(
        id=uuid.uuid4(), name=path.name, source=str(path), content_hash=parsed.content_hash
    )
    for index, (text, embedding) in enumerate(zip(chunk_texts, embeddings, strict=True)):
        document.chunks.append(
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=index,
                content=text,
                embedding=embedding,
            )
        )
    db_session.add(document)
    await db_session.commit()
    return document


@pytest.mark.integration
async def test_ingestion_flow_persists_document_and_chunks_with_real_embeddings(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    path = tmp_path / "rate-limits-and-auth.md"
    path.write_bytes(_FIXTURE_MARKDOWN.encode("utf-8"))
    expected_content_hash = get_parser(path).parse(path).content_hash

    document = await _ingest(path, db_session)

    assert document.content_hash == expected_content_hash
    assert len(document.chunks) >= 2
    assert [c.chunk_index for c in document.chunks] == list(range(len(document.chunks)))
    for chunk in document.chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == settings.embedding_dimension
        assert chunk.content.strip() != ""


@pytest.mark.integration
async def test_ingested_chunks_are_retrievable_via_pgvector_retriever(
    tmp_path: Path, db_session: AsyncSession
) -> None:
    """Capstone check: proves the ingest -> retrieve loop actually works end-to-end, not just
    that rows got written."""
    path = tmp_path / "rate-limits-and-auth.md"
    path.write_bytes(_FIXTURE_MARKDOWN.encode("utf-8"))

    document = await _ingest(path, db_session)

    embedder = get_embedding_model()
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
    """docs/ARCHITECTURE.md section 3.1: "content_hash is the natural dedupe key" for
    idempotent re-ingestion - nothing previously exercised the DB actually enforcing this.
    Confirms the unique constraint (uq_documents_content_hash) really does reject a second
    Document row with the same content_hash, rather than silently duplicating data.
    """
    path = tmp_path / "rate-limits-and-auth.md"
    path.write_bytes(_FIXTURE_MARKDOWN.encode("utf-8"))

    await _ingest(path, db_session)

    with pytest.raises(IntegrityError):
        await _ingest(path, db_session)

    # Required after a failed flush/commit so the outer test-isolation transaction (see
    # tests/integration/conftest.py) can still clean up normally.
    await db_session.rollback()
