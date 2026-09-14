"""RAG service orchestrator: question -> embedding -> retrieval -> prompt -> LLM -> citations.

Contains no HTTP, SQL, or SDK calls - it only composes the Protocols, wired in by the caller
(see dependencies.py). Exception: `langsmith.traceable` below is applied directly since it's
cross-cutting instrumentation, not a business dependency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from langsmith import traceable

from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.config import settings
from knowledge_assistant.domain import Answer, LLMResponse, RetrievedChunk
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.retrieval.protocols import Retriever

# No config field for this yet - a candidate for settings.llm_max_tokens later.
_DEFAULT_MAX_TOKENS = 512


@dataclass(frozen=True, slots=True)
class QueryTrace:
    """One answer_question call's Answer plus the chunks/LLMResponse/timings behind it - used
    by the evaluation runner to score retrieval quality, groundedness, latency, and cost."""

    answer: Answer
    chunks: list[RetrievedChunk]
    llm_response: LLMResponse
    retrieval_latency_ms: float
    total_latency_ms: float


class RAGService:
    """Orchestrates one question -> Answer round trip via injected Protocols."""

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        retriever: Retriever,
        prompt_builder: PromptBuilder,
        llm_client: LLMClient,
        citation_extractor: CitationExtractor,
    ) -> None:
        self._embedding_model = embedding_model
        self._retriever = retriever
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client
        self._citation_extractor = citation_extractor

    async def answer_question(self, question: str) -> Answer:
        trace = await self.answer_question_with_trace(question)
        return trace.answer

    @traceable(name="RAGService.answer_question_with_trace", run_type="chain")
    async def answer_question_with_trace(self, question: str) -> QueryTrace:
        """Same pipeline as answer_question, plus the retrieved chunks, raw LLMResponse, and
        per-stage latency - used by the evaluation runner, not the API route.

        `@traceable` is a no-op with no network calls unless LangSmith tracing is enabled
        (settings.langsmith_api_key set - see dependencies.py); verified against the SDK.
        """
        total_start = time.perf_counter()
        query_embedding = (await self._embedding_model.embed([question]))[0]

        # Empty chunks flow through unchanged - prompt_builder already handles that case.
        retrieval_start = time.perf_counter()
        chunks = await self._retriever.search(
            query_embedding, settings.top_k, settings.similarity_threshold
        )
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

        prompt = self._prompt_builder.build(question, chunks)
        llm_response = await self._llm_client.generate(prompt, max_tokens=_DEFAULT_MAX_TOKENS)

        answer = self._citation_extractor.extract(llm_response.answer, chunks)
        total_latency_ms = (time.perf_counter() - total_start) * 1000

        return QueryTrace(
            answer=answer,
            chunks=chunks,
            llm_response=llm_response,
            retrieval_latency_ms=retrieval_latency_ms,
            total_latency_ms=total_latency_ms,
        )
