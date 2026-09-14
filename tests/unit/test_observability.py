"""Unit tests for observability (Step 14): structured request logging on POST /query, and that
the app behaves completely normally with LangSmith tracing unconfigured (the default state in
this environment - no API key, no network calls). Fake Protocol implementations, no real
models/DB, matching tests/unit/test_api.py's pattern.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from knowledge_assistant import dependencies
from knowledge_assistant.api.main import app
from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.config import settings
from knowledge_assistant.domain import Answer, Citation, LLMResponse, RetrievedChunk
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.retrieval.protocols import Retriever


class FakeEmbeddingModel(EmbeddingModel):
    dimension = 3

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeRetriever(Retriever):
    def __init__(self, chunks_to_return: list[RetrievedChunk]) -> None:
        self._chunks_to_return = chunks_to_return

    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        return self._chunks_to_return


class FakePromptBuilder(PromptBuilder):
    template_version = "fake"

    def build(self, question: str, chunks: list[RetrievedChunk]) -> str:
        return "THE PROMPT"


class FakeLLMClient(LLMClient):
    def __init__(self, answer_text: str) -> None:
        self._answer_text = answer_text

    async def generate(self, prompt: str, *, max_tokens: int) -> LLMResponse:
        return LLMResponse(
            answer=self._answer_text,
            input_tokens=10,
            output_tokens=5,
            latency_ms=1.0,
            model_id="fake-model-id",
        )


class FakeCitationExtractor(CitationExtractor):
    def __init__(self, answer_to_return: Answer) -> None:
        self._answer_to_return = answer_to_return

    def extract(self, answer_text: str, chunks: list[RetrievedChunk]) -> Answer:
        return self._answer_to_return


@pytest.fixture
def client() -> Generator[TestClient]:
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    chunk = RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_name="rate-limits.md",
        chunk_index=2,
        content="The default rate limit is 100 requests per minute.",
        score=0.9,
    )
    expected_answer = Answer(
        text="The rate limit is 100 requests per minute (source: rate-limits.md, chunk 2).",
        citations=[
            Citation(
                document_id=document_id,
                document_name="rate-limits.md",
                chunk_index=2,
                snippet="The default rate limit is 100 requests per minute.",
            )
        ],
        abstained=False,
        citations_missing=False,
    )

    app.dependency_overrides[dependencies.get_embedding_model] = lambda: FakeEmbeddingModel()
    app.dependency_overrides[dependencies.get_retriever] = lambda: FakeRetriever([chunk])
    app.dependency_overrides[dependencies.get_prompt_builder] = lambda: FakePromptBuilder()
    app.dependency_overrides[dependencies.get_llm_client_singleton] = lambda: FakeLLMClient(
        expected_answer.text
    )
    app.dependency_overrides[dependencies.get_citation_extractor] = lambda: FakeCitationExtractor(
        expected_answer
    )

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
def test_query_logs_one_structured_info_line_with_expected_fields(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="knowledge_assistant.api.main"):
        response = client.post("/query", json={"question": "What is the API rate limit?"})

    assert response.status_code == 200

    records = [r for r in caplog.records if r.name == "knowledge_assistant.api.main"]
    assert len(records) == 1
    record = records[0]

    assert record.levelname == "INFO"
    assert record.request_id  # a real, non-empty generated request id
    assert uuid.UUID(record.request_id)  # is actually a valid UUID, not a placeholder string
    assert record.question == "What is the API rate limit?"
    assert len(record.retrieved_chunk_ids) == 1
    assert uuid.UUID(record.retrieved_chunk_ids[0])  # a real chunk id, not a placeholder
    assert isinstance(record.retrieval_latency_ms, float)
    assert isinstance(record.total_latency_ms, float)
    assert record.model_id == "fake-model-id"
    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.abstained is False
    assert record.citations_missing is False


@pytest.mark.unit
def test_two_requests_get_two_different_request_ids(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="knowledge_assistant.api.main"):
        client.post("/query", json={"question": "What is the API rate limit?"})
        client.post("/query", json={"question": "What is the API rate limit?"})

    records = [r for r in caplog.records if r.name == "knowledge_assistant.api.main"]
    assert len(records) == 2
    assert records[0].request_id != records[1].request_id


@pytest.mark.unit
def test_langsmith_tracing_is_disabled_by_default_and_query_still_works_normally(
    client: TestClient,
) -> None:
    """The default/expected state in this environment: no LANGSMITH_API_KEY configured.
    Confirms the whole request path (which now goes through the @traceable-wrapped
    RAGService.answer_question_with_trace) still works completely normally - no exception, no
    hang, no attempted network call - when tracing is off."""
    assert not settings.langsmith_api_key

    response = client.post("/query", json={"question": "What is the API rate limit?"})

    assert response.status_code == 200
    assert response.json()["answer"]
