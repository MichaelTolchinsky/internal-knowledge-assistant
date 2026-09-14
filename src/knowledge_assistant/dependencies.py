"""Composition root: the single place concrete Protocol implementations get wired together.

Singletons are lazy (built on first call, cached after) via `lru_cache` - not at import time -
so importing this module never loads a model. This matters for tests that override these
accessors with fakes (e.g. tests/unit/test_api.py): the real embedding/LLM models are never
constructed at all when overridden. Query-time and ingestion-time embedding share the same
cached instance so vectors stay comparable.

PgVectorRetriever is NOT a singleton - it needs a per-request AsyncSession, so `get_retriever`
is a FastAPI dependency instead of a cached instance.
"""

from __future__ import annotations

import os
from functools import lru_cache

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

# Optional LangSmith tracing: a no-op unless settings.langsmith_api_key is set. `setdefault` so
# real operator env vars aren't clobbered.
if settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)


@lru_cache
def get_embedding_model() -> EmbeddingModel:
    return HuggingFaceEmbeddingModel()


@lru_cache
def get_llm_client_singleton() -> LLMClient:
    return get_llm_client(settings)


@lru_cache
def get_prompt_builder() -> PromptBuilder:
    return PromptBuilderV1()


@lru_cache
def get_citation_extractor() -> CitationExtractor:
    return TextCitationExtractor()


def get_retriever(session: AsyncSession = Depends(get_session)) -> Retriever:
    """FastAPI dependency: a fresh PgVectorRetriever per request."""
    return PgVectorRetriever(session)
