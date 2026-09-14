"""Unit tests for the /query API route (tests/unit - fake Protocol implementations injected via
FastAPI's dependency_overrides, no real models/DB; the real end-to-end test comes in a later
sub-step)."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from knowledge_assistant import dependencies
from knowledge_assistant.api.main import app
from knowledge_assistant.citations.protocols import CitationExtractor
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
            model_id="fake-model",
        )


class FakeCitationExtractor(CitationExtractor):
    def __init__(self, answer_to_return: Answer) -> None:
        self._answer_to_return = answer_to_return

    def extract(self, answer_text: str, chunks: list[RetrievedChunk]) -> Answer:
        return self._answer_to_return


@pytest.fixture
def client() -> Generator[TestClient]:
    document_id = uuid.uuid4()
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
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
def test_query_returns_200_with_expected_shape(client: TestClient) -> None:
    response = client.post("/query", json={"question": "What is the API rate limit?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == (
        "The rate limit is 100 requests per minute (source: rate-limits.md, chunk 2)."
    )
    assert body["abstained"] is False
    assert body["citations_missing"] is False
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["document_name"] == "rate-limits.md"
    assert citation["chunk_index"] == 2
    assert citation["snippet"] == "The default rate limit is 100 requests per minute."
    assert "document_id" in citation


@pytest.mark.unit
def test_query_citations_reflect_the_citation_extractors_output(client: TestClient) -> None:
    response = client.post("/query", json={"question": "What is the API rate limit?"})

    citations = response.json()["citations"]
    assert citations != []
    assert citations[0]["document_name"] == "rate-limits.md"
    assert citations[0]["chunk_index"] == 2


@pytest.mark.unit
def test_query_with_empty_question_returns_422(client: TestClient) -> None:
    response = client.post("/query", json={"question": ""})

    assert response.status_code == 422


@pytest.mark.unit
def test_query_with_whitespace_only_question_returns_422(client: TestClient) -> None:
    response = client.post("/query", json={"question": "   "})

    assert response.status_code == 422
