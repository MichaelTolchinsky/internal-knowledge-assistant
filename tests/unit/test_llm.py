"""Unit tests for LocalLLMClient and get_llm_client.

Loads the real model (no mocking the inference path, same philosophy as the embedding tests) -
first run downloads the ~1GB Qwen2.5-0.5B-Instruct model from HuggingFace, cached afterward on
~/.cache/huggingface. Module-scoped fixture so the (slow) model load happens once for the whole
file, not once per test.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from knowledge_assistant.config import settings
from knowledge_assistant.llm.factory import get_llm_client
from knowledge_assistant.llm.local import LocalLLMClient

pytestmark = pytest.mark.timeout(180)


@pytest.fixture(scope="module")
def client() -> LocalLLMClient:
    return LocalLLMClient()


@pytest.mark.unit
async def test_generate_returns_non_empty_answer(client: LocalLLMClient) -> None:
    response = await client.generate("What is the capital of France?", max_tokens=50)

    assert response.answer.strip() != ""


@pytest.mark.unit
async def test_token_counts_are_populated_and_sane(client: LocalLLMClient) -> None:
    max_tokens = 30

    response = await client.generate("What is the capital of France?", max_tokens=max_tokens)

    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert response.output_tokens <= max_tokens


@pytest.mark.unit
async def test_latency_ms_is_populated_and_positive(client: LocalLLMClient) -> None:
    response = await client.generate("What is the capital of France?", max_tokens=20)

    assert response.latency_ms > 0


@pytest.mark.unit
async def test_model_id_matches_settings(client: LocalLLMClient) -> None:
    response = await client.generate("What is the capital of France?", max_tokens=10)

    assert response.model_id == settings.local_llm_model_name


@pytest.mark.unit
def test_get_llm_client_returns_local_client_for_local_provider() -> None:
    fake_settings = SimpleNamespace(
        llm_provider="local", local_llm_model_name=settings.local_llm_model_name
    )

    result = get_llm_client(fake_settings)

    assert isinstance(result, LocalLLMClient)


@pytest.mark.unit
def test_get_llm_client_raises_for_unsupported_provider() -> None:
    fake_settings = SimpleNamespace(llm_provider="bedrock", local_llm_model_name="unused")

    with pytest.raises(ValueError, match="bedrock"):
        get_llm_client(fake_settings)
