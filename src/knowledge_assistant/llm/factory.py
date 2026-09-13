"""Composition point for LLMClient implementations.

Deliberately minimal - a placeholder until the API/composition-root step wires up embeddings/
retriever the same way. Only "local" is supported right now; Bedrock is a later step, not a
stub here (see docs/CODING-GUIDELINES.md section 3's "wire concrete implementations in one
composition point" guidance).
"""

from __future__ import annotations

from knowledge_assistant.config import Settings
from knowledge_assistant.llm.local import LocalLLMClient
from knowledge_assistant.llm.protocols import LLMClient


def get_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "local":
        return LocalLLMClient(settings.local_llm_model_name)

    raise ValueError(
        f"Unsupported llm_provider: {settings.llm_provider!r}. Only 'local' is implemented - "
        f"Bedrock support is not yet implemented."
    )
