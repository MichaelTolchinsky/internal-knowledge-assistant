"""Smoke tests confirming dependencies.py's accessors are real singletons.

Importing this module triggers real model loads (HuggingFaceEmbeddingModel, LocalLLMClient) via
dependencies.py's module-level construction - consistent with this project's "no mocking the
real model" testing philosophy elsewhere (Step 5/8 embedding/LLM tests).
"""

from __future__ import annotations

import pytest

from knowledge_assistant import dependencies

pytestmark = pytest.mark.timeout(120)


@pytest.mark.unit
def test_embedding_model_is_a_singleton() -> None:
    assert dependencies.get_embedding_model() is dependencies.get_embedding_model()


@pytest.mark.unit
def test_llm_client_is_a_singleton() -> None:
    assert dependencies.get_llm_client_singleton() is dependencies.get_llm_client_singleton()


@pytest.mark.unit
def test_prompt_builder_is_a_singleton() -> None:
    assert dependencies.get_prompt_builder() is dependencies.get_prompt_builder()


@pytest.mark.unit
def test_citation_extractor_is_a_singleton() -> None:
    assert dependencies.get_citation_extractor() is dependencies.get_citation_extractor()
