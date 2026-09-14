"""RAG service orchestrator: the query-time pipeline from docs/ARCHITECTURE.md section 3.2
(question -> embedding -> retrieval -> prompt -> LLM -> citations -> Answer).

Per docs/CODING-GUIDELINES.md section 2: this module contains no HTTP concerns, no SQL, and no
Bedrock/transformers SDK calls itself - it composes the Protocols only. Concrete
implementations are wired in by the caller (see dependencies.py), never imported here. The one
deliberate exception is `langsmith.traceable` below (Step 14, observability) - a cross-cutting
instrumentation decorator, not a business dependency, so it's applied directly here rather than
injected like the Protocols are.
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

# No config field for this yet (checked config.py/.env.example - neither has one). Hardcoded
# here as a reasonable default for a grounded, citation-aware paragraph answer; a candidate for
# a future `settings.llm_max_tokens` field if/when it needs to be tuned per the evaluation
# experiment workflow (docs/CODING-GUIDELINES.md section 6).
_DEFAULT_MAX_TOKENS = 512


@dataclass(frozen=True, slots=True)
class QueryTrace:
    """Diagnostic detail behind one answer_question call: the Answer plus the intermediate
    chunks/LLMResponse/timings that produced it. Not a domain type (docs/CODING-GUIDELINES.md
    section 5's domain types are the core RAG output shape) - this is orchestration-level
    diagnostic detail, used by the Step 13 evaluation runner to score retrieval quality,
    groundedness, latency, and cost without duplicating RAGService's own orchestration logic
    elsewhere (see evaluation/runner.py)."""

    answer: Answer
    chunks: list[RetrievedChunk]
    llm_response: LLMResponse
    retrieval_latency_ms: float
    total_latency_ms: float


class RAGService:
    """Orchestrates one question -> Answer round trip. Holds no HTTP/SQL/SDK code - every
    external boundary is a Protocol, injected by the caller (see dependencies.py)."""

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
        """Same pipeline as answer_question, but also returns the retrieved chunks, the raw
        LLMResponse (token counts), and latency broken down by stage - the API route doesn't
        need this, the evaluation runner does.

        Wrapped in `@traceable`: a no-op with zero network calls unless LangSmith tracing is
        actually enabled (settings.langsmith_api_key configured - see dependencies.py). Verified
        directly against the installed langsmith SDK, not assumed from docs: with no
        LANGSMITH_TRACING/LANGSMITH_API_KEY env vars set,
        `langsmith.utils.tracing_is_enabled()` returns False and the decorator short-circuits
        to a plain passthrough call, sync or async, with no import errors or attempted requests.
        """
        total_start = time.perf_counter()
        query_embedding = (await self._embedding_model.embed([question]))[0]

        # Empty results (no chunks pass similarity_threshold, or nothing retrieved at all) flow
        # through unchanged - prompt_builder's <no_context> handling (Step 7) already covers an
        # empty chunks list, no special-casing needed here.
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
