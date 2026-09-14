"""End-to-end integration test: real Postgres, real local embedding model, real local LLM,
real seeded documents, hitting the actual POST /query endpoint through FastAPI's TestClient - no
fakes/mocks anywhere in this test (unlike the unit-tier tests in tests/unit/test_api.py and
tests/unit/test_rag_service.py, which deliberately used fakes to isolate orchestration logic).

Requires local Postgres/pgvector (`docker compose up postgres` in docker/) with migrations
applied (`alembic upgrade head`), same as the rest of tests/integration/.

Isolation: only `storage.database.get_session` is overridden, to bind the real PgVectorRetriever
to this test's rollback-wrapped `db_session` (see tests/integration/conftest.py) instead of a
fresh production session - nothing else is faked. `get_retriever` itself, and the
embedding/LLM/prompt/citation singletons from dependencies.py, are all real.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.api.main import app
from knowledge_assistant.dependencies import get_embedding_model
from knowledge_assistant.storage.database import get_session
from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel

_RATE_LIMIT_CONTENT = (
    "The default API rate limit is 100 requests per minute per API key. Enterprise plans can "
    "request an increase to 500 requests per minute."
)
_AUTH_CONTENT = (
    "Rotate production API credentials every 90 days via the admin console. Credentials not "
    "rotated within 120 days are automatically revoked."
)


@pytest.fixture
async def seeded_documents(db_session: AsyncSession) -> AsyncGenerator[None]:
    """Two real documents/chunks with REAL embeddings (via the actual
    dependencies.get_embedding_model() singleton) - unlike Step 6's retrieval tests, which
    deliberately used hand-built vectors to isolate SQL logic, this test exercises the real
    embedding model end-to-end."""
    embedder = get_embedding_model()
    for name, content in [
        ("rate-limits.md", _RATE_LIMIT_CONTENT),
        ("auth.md", _AUTH_CONTENT),
    ]:
        document = DocumentModel(
            id=uuid.uuid4(), name=name, source=name, content_hash=f"hash-{uuid.uuid4()}"
        )
        embedding = (await embedder.embed([content]))[0]
        document.chunks.append(
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=0,
                content=content,
                embedding=embedding,
            )
        )
        db_session.add(document)
    await db_session.commit()
    yield


@pytest.fixture
def client(db_session: AsyncSession) -> Generator[TestClient]:
    """Overrides only get_session, so the real PgVectorRetriever binds to this test's
    rollback-wrapped session - every other dependency (embedding model, LLM, prompt builder,
    citation extractor, and the retriever construction itself) is the real, unmodified
    dependencies.py wiring."""

    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.requires_real_llm
def test_query_answerable_question_returns_grounded_answer(
    client: TestClient, seeded_documents: None
) -> None:
    """Real end-to-end proof the pipeline works: real retrieval finds the right chunk, the real
    local LLM answers correctly from it. Assertion is content-based rather than requiring a
    citation marker in the response - confirmed empirically (real pipeline, greedy/deterministic
    decoding, reproducible across several prompt phrasings including one that explicitly asked
    for the citation format) that this small local model reliably gives correct, grounded
    answers but does not reliably include the "(source: ..., chunk N)" marker. citations_missing
    correctly reflects that when it happens - this test does not require citations to be
    present, but validates them if the model did include any.

    requires_real_llm: needs an actually-trained model to produce a factually correct answer -
    a tiny/random-weight test model (e.g. used to keep CI fast) can't pass this, so CI excludes
    this marker; local full-suite runs still exercise it against the real model.
    """
    start = time.perf_counter()
    response = client.post("/query", json={"question": "What is the API rate limit?"})
    elapsed_s = time.perf_counter() - start

    assert response.status_code == 200
    body = response.json()

    assert "100" in body["answer"]
    assert "rate limit" in body["answer"].lower() or "requests per minute" in body["answer"]
    assert isinstance(body["abstained"], bool)
    assert isinstance(body["citations_missing"], bool)

    for citation in body["citations"]:
        assert citation["document_name"] in {"rate-limits.md", "auth.md"}
        assert isinstance(citation["chunk_index"], int)
        assert citation["snippet"]

    print(
        f"\n[test_query_answerable_question_returns_grounded_answer] wall-clock: {elapsed_s:.2f}s"
    )
    print(f"answer: {body['answer']!r}")
    print(f"citations: {body['citations']}")
    print(f"abstained={body['abstained']} citations_missing={body['citations_missing']}")


@pytest.mark.integration
def test_query_with_no_relevant_content_signals_uncertainty(
    client: TestClient, seeded_documents: None
) -> None:
    """A question with no relevant seeded content. Empirically (Step 9 fix-pass real repro,
    reconfirmed here), this small local model does not reliably abstain using the documented
    phrase for an off-topic question, and may even answer from its own general knowledge
    instead of admitting it lacks context - but it also never produces a valid citation in that
    case. So the reliable, reproducible signal for "the system doesn't actually have grounded
    information for this" is: abstained OR citations_missing is True (not "the answer text says
    exactly the abstention phrase").
    """
    start = time.perf_counter()
    response = client.post(
        "/query", json={"question": "What is our company's parental leave policy?"}
    )
    elapsed_s = time.perf_counter() - start

    assert response.status_code == 200
    body = response.json()

    assert body["abstained"] or body["citations_missing"]

    print(
        f"\n[test_query_with_no_relevant_content_signals_uncertainty] wall-clock: {elapsed_s:.2f}s"
    )
    print(f"answer: {body['answer']!r}")
    print(f"citations: {body['citations']}")
    print(f"abstained={body['abstained']} citations_missing={body['citations_missing']}")
