"""FastAPI application entrypoint.

`/health` for boot checks, `/query` for the core RAG flow (see docs/ARCHITECTURE.md section 6).
Route handlers stay thin - request -> RAGService.answer_question_with_trace() -> structured log
-> response mapping only, no business logic here (that lives in rag_service.py) per
docs/CODING-GUIDELINES.md section 2's separation of concerns. Structured request logging (Step
14, observability) lives here rather than in rag_service.py for the same reason: it's an HTTP-
layer/request concern (request_id), not RAG orchestration logic.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Depends, FastAPI

from knowledge_assistant import dependencies
from knowledge_assistant.api.schemas import CitationResponse, QueryRequest, QueryResponse
from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.rag_service import RAGService
from knowledge_assistant.retrieval.protocols import Retriever

logger = logging.getLogger(__name__)

app = FastAPI(title="Internal Knowledge Assistant")


def get_rag_service(
    embedding_model: EmbeddingModel = Depends(dependencies.get_embedding_model),
    retriever: Retriever = Depends(dependencies.get_retriever),
    prompt_builder: PromptBuilder = Depends(dependencies.get_prompt_builder),
    llm_client: LLMClient = Depends(dependencies.get_llm_client_singleton),
    citation_extractor: CitationExtractor = Depends(dependencies.get_citation_extractor),
) -> RAGService:
    """Per-request RAGService, composed from the singletons/per-request deps in
    dependencies.py. Chains get_retriever (itself Depends-based, per-request AsyncSession)
    alongside the process-lifetime singletons."""
    return RAGService(embedding_model, retriever, prompt_builder, llm_client, citation_extractor)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest, rag_service: RAGService = Depends(get_rag_service)
) -> QueryResponse:
    # Vanilla FastAPI/Starlette has no built-in per-request ID (verified - Request/Response
    # carry nothing like this by default), so one is generated here per docs/ARCHITECTURE.md
    # section 7's "request ID" tracking requirement.
    request_id = str(uuid.uuid4())

    trace = await rag_service.answer_question_with_trace(request.question)
    answer = trace.answer

    # One structured log line per successful request, per docs/ARCHITECTURE.md section 7:
    # request ID, question, retrieved chunk IDs, retrieval latency, model, token usage, LLM
    # latency, total latency. `extra=` keeps these as real structured fields on the LogRecord
    # (parseable by a log processor/JSON formatter), not smashed into an f-string - trace only
    # exposes retrieval_latency_ms and total_latency_ms (not a separate LLM-only latency), so
    # total_latency_ms stands in for "LLM latency" here (retrieval + embed + LLM combined minus
    # the already-reported retrieval_latency_ms leaves LLM+embed, but that split isn't tracked
    # separately - see rag_service.py's QueryTrace).
    logger.info(
        "query completed: request_id=%s abstained=%s citations_missing=%s",
        request_id,
        answer.abstained,
        answer.citations_missing,
        extra={
            "request_id": request_id,
            "question": request.question,
            "retrieved_chunk_ids": [str(chunk.chunk_id) for chunk in trace.chunks],
            "retrieval_latency_ms": trace.retrieval_latency_ms,
            "total_latency_ms": trace.total_latency_ms,
            "model_id": trace.llm_response.model_id,
            "input_tokens": trace.llm_response.input_tokens,
            "output_tokens": trace.llm_response.output_tokens,
            "abstained": answer.abstained,
            "citations_missing": answer.citations_missing,
        },
    )

    return QueryResponse(
        answer=answer.text,
        citations=[
            CitationResponse(
                document_id=citation.document_id,
                document_name=citation.document_name,
                chunk_index=citation.chunk_index,
                snippet=citation.snippet,
            )
            for citation in answer.citations
        ],
        abstained=answer.abstained,
        citations_missing=answer.citations_missing,
    )
