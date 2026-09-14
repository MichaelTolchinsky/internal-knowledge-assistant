"""Unit tests for RAGService (tests/unit - fake Protocol implementations, no real models/DB;
the real end-to-end test lives in a later sub-step)."""

from __future__ import annotations

import uuid

import pytest

from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.config import settings
from knowledge_assistant.domain import Answer, Citation, LLMResponse, RetrievedChunk
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.rag_service import RAGService
from knowledge_assistant.retrieval.protocols import Retriever


class FakeEmbeddingModel(EmbeddingModel):
    dimension = 3

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeRetriever(Retriever):
    def __init__(self, chunks_to_return: list[RetrievedChunk]) -> None:
        self._chunks_to_return = chunks_to_return
        self.calls: list[tuple[list[float], int, float | None]] = []

    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        self.calls.append((query_embedding, top_k, similarity_threshold))
        return self._chunks_to_return


class FakePromptBuilder(PromptBuilder):
    template_version = "fake"

    def __init__(self, prompt_to_return: str) -> None:
        self._prompt_to_return = prompt_to_return
        self.calls: list[tuple[str, list[RetrievedChunk]]] = []

    def build(self, question: str, chunks: list[RetrievedChunk]) -> str:
        self.calls.append((question, chunks))
        return self._prompt_to_return


class FakeLLMClient(LLMClient):
    def __init__(self, response_to_return: LLMResponse) -> None:
        self._response_to_return = response_to_return
        self.calls: list[tuple[str, int]] = []

    async def generate(self, prompt: str, *, max_tokens: int) -> LLMResponse:
        self.calls.append((prompt, max_tokens))
        return self._response_to_return


class FakeCitationExtractor(CitationExtractor):
    def __init__(self, answer_to_return: Answer) -> None:
        self._answer_to_return = answer_to_return
        self.calls: list[tuple[str, list[RetrievedChunk]]] = []

    def extract(self, answer_text: str, chunks: list[RetrievedChunk]) -> Answer:
        self.calls.append((answer_text, chunks))
        return self._answer_to_return


def _chunk(
    document_name: str, chunk_index: int, content: str, score: float = 0.9
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        chunk_index=chunk_index,
        content=content,
        score=score,
    )


def _llm_response(answer: str) -> LLMResponse:
    return LLMResponse(
        answer=answer, input_tokens=10, output_tokens=5, latency_ms=1.0, model_id="fake-model"
    )


@pytest.mark.unit
async def test_answer_question_calls_each_dependency_in_order_with_correct_arguments() -> None:
    chunks = [_chunk("rate-limits.md", 2, "The default rate limit is 100 requests per minute.")]
    expected_answer = Answer(
        text="The rate limit is 100 req/min.",
        citations=[
            Citation(
                document_id=chunks[0].document_id,
                document_name="rate-limits.md",
                chunk_index=2,
                snippet="The default rate limit is 100 requests per minute.",
            )
        ],
        abstained=False,
        citations_missing=False,
    )

    embedding_model = FakeEmbeddingModel()
    retriever = FakeRetriever(chunks_to_return=chunks)
    prompt_builder = FakePromptBuilder(prompt_to_return="THE PROMPT")
    llm_client = FakeLLMClient(response_to_return=_llm_response("The rate limit is 100 req/min."))
    citation_extractor = FakeCitationExtractor(answer_to_return=expected_answer)

    service = RAGService(embedding_model, retriever, prompt_builder, llm_client, citation_extractor)
    result = await service.answer_question("What is the API rate limit?")

    # embedding_model got the raw question
    assert embedding_model.calls == [["What is the API rate limit?"]]

    # retriever got the embedding's actual output, plus the real configured settings
    assert len(retriever.calls) == 1
    query_embedding, top_k, similarity_threshold = retriever.calls[0]
    assert query_embedding == [0.1, 0.2, 0.3]
    assert top_k == settings.top_k
    assert similarity_threshold == settings.similarity_threshold

    # prompt_builder got the retriever's actual output
    assert prompt_builder.calls == [("What is the API rate limit?", chunks)]

    # llm_client got the prompt_builder's actual output
    assert llm_client.calls == [("THE PROMPT", 512)]

    # citation_extractor got the LLM's answer text and the retriever's actual output
    assert citation_extractor.calls == [("The rate limit is 100 req/min.", chunks)]

    # the final Answer is exactly what the citation_extractor produced
    assert result is expected_answer


@pytest.mark.unit
async def test_answer_question_handles_empty_retrieval_without_crashing() -> None:
    expected_answer = Answer(
        text="I don't have enough information in the provided documents to answer this "
        "confidently.",
        citations=[],
        abstained=True,
        citations_missing=False,
    )

    embedding_model = FakeEmbeddingModel()
    retriever = FakeRetriever(chunks_to_return=[])
    prompt_builder = FakePromptBuilder(prompt_to_return="THE PROMPT WITH NO CONTEXT")
    llm_client = FakeLLMClient(response_to_return=_llm_response(expected_answer.text))
    citation_extractor = FakeCitationExtractor(answer_to_return=expected_answer)

    service = RAGService(embedding_model, retriever, prompt_builder, llm_client, citation_extractor)
    result = await service.answer_question("What is our parental leave policy?")

    assert prompt_builder.calls == [("What is our parental leave policy?", [])]
    assert citation_extractor.calls == [(expected_answer.text, [])]
    assert result is expected_answer
