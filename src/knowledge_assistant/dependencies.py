"""Composition root: the single place concrete Protocol implementations get wired together.

Per docs/CODING-GUIDELINES.md section 3 ("wire concrete implementations in one composition
point... not scattered imports of concrete classes throughout the codebase"). The next step
(RAG service + API routes) should import accessors from here, not construct
HuggingFaceEmbeddingModel/LocalLLMClient/etc. directly.

Most implementations are process-lifetime singletons, built once at import time - this matters
for HuggingFaceEmbeddingModel and LocalLLMClient in particular, since constructing them loads a
model (the expensive part - see embeddings/huggingface.py and llm/local.py). It also resolves
the other Step 5 TODO: query-time and ingestion-time embedding must share the same
HuggingFaceEmbeddingModel instance so vectors stay comparable (see Step 1-3 Learning Gate).

PgVectorRetriever is deliberately NOT a singleton - it needs a per-request AsyncSession, so
`get_retriever` is a FastAPI dependency (via `Depends(get_session)`) instead of a module-level
instance.
"""

from __future__ import annotations

import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.citations.text_extractor import TextCitationExtractor
from knowledge_assistant.config import settings
from knowledge_assistant.embeddings.huggingface import HuggingFaceEmbeddingModel
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.factory import get_llm_client
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.prompts.v1 import PromptBuilderV1
from knowledge_assistant.retrieval.pgvector import PgVectorRetriever
from knowledge_assistant.retrieval.protocols import Retriever
from knowledge_assistant.storage.database import get_session

_embedding_model = HuggingFaceEmbeddingModel()
_llm_client = get_llm_client(settings)
_prompt_builder = PromptBuilderV1()
_citation_extractor = TextCitationExtractor()

# Optional LangSmith tracing (docs/ARCHITECTURE.md section 7). The `@traceable` decorator on
# RAGService.answer_question_with_trace is always present in the source (see rag_service.py) -
# it's a no-op with zero network calls whenever LangSmith's own env-based check
# (`langsmith.utils.tracing_is_enabled()`, reads LANGSMITH_TRACING/LANGSMITH_API_KEY) says
# tracing is off, which is exactly the state when settings.langsmith_api_key is unset - the
# default/expected case in this environment. `setdefault` so an operator's own real env vars
# (if already exported) aren't clobbered by this settings-derived wiring.
if settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)


def get_embedding_model() -> EmbeddingModel:
    """The single shared HuggingFaceEmbeddingModel instance - reused for both query-time and
    ingestion-time embedding so vectors stay comparable."""
    return _embedding_model


def get_llm_client_singleton() -> LLMClient:
    """The single shared LLMClient instance, built via llm.factory.get_llm_client at import
    time using settings.llm_provider."""
    return _llm_client


def get_prompt_builder() -> PromptBuilder:
    """The single shared PromptBuilderV1 instance."""
    return _prompt_builder


def get_citation_extractor() -> CitationExtractor:
    """The single shared TextCitationExtractor instance."""
    return _citation_extractor


def get_retriever(session: AsyncSession = Depends(get_session)) -> Retriever:
    """FastAPI dependency: a fresh PgVectorRetriever per request, bound to that request's
    AsyncSession - not a singleton, unlike the other accessors in this module."""
    return PgVectorRetriever(session)
