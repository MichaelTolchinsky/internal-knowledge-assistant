"""FastAPI application entrypoint.

`/health` for boot checks, `/query` for the core RAG flow (see docs/ARCHITECTURE.md section 6).
Route handlers stay thin - request -> RAGService.answer_question() -> response mapping only, no
business logic here (that lives in rag_service.py) per docs/CODING-GUIDELINES.md section 2's
separation of concerns.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from knowledge_assistant import dependencies
from knowledge_assistant.api.schemas import CitationResponse, QueryRequest, QueryResponse
from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.rag_service import RAGService
from knowledge_assistant.retrieval.protocols import Retriever

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
    answer = await rag_service.answer_question(request.question)
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
