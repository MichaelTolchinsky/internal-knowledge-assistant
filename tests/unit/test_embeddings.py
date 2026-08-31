"""Unit tests for HuggingFaceEmbeddingModel.

These load the real sentence-transformers model (no mocking the inference path, per the
approved task) - first run downloads ~80MB from HuggingFace, cached afterward on
~/.cache/huggingface. Module-scoped fixture so the (slow) model load happens once for the
whole file, not once per test.
"""

from __future__ import annotations

import pytest

from knowledge_assistant.config import settings
from knowledge_assistant.embeddings.huggingface import HuggingFaceEmbeddingModel

pytestmark = pytest.mark.timeout(120)


@pytest.fixture(scope="module")
def model() -> HuggingFaceEmbeddingModel:
    return HuggingFaceEmbeddingModel()


@pytest.mark.unit
def test_dimension_matches_settings(model: HuggingFaceEmbeddingModel) -> None:
    assert model.dimension == settings.embedding_dimension


@pytest.mark.unit
def test_embed_returns_one_vector_per_text_of_configured_dimension(
    model: HuggingFaceEmbeddingModel,
) -> None:
    vectors = model.embed(["some text"])

    assert len(vectors) == 1
    assert isinstance(vectors[0], list)
    assert all(isinstance(x, float) for x in vectors[0])
    assert len(vectors[0]) == settings.embedding_dimension


@pytest.mark.unit
def test_embed_is_deterministic(model: HuggingFaceEmbeddingModel) -> None:
    first = model.embed(["Rotate production API credentials regularly."])[0]
    second = model.embed(["Rotate production API credentials regularly."])[0]

    # sentence-transformers inference on CPU/MPS is deterministic in practice, but float
    # accumulation order isn't guaranteed bit-identical across runs/backends - compare with a
    # tight tolerance rather than exact equality.
    assert first == pytest.approx(second, abs=1e-6)


@pytest.mark.unit
def test_embed_differs_for_semantically_different_texts(
    model: HuggingFaceEmbeddingModel,
) -> None:
    vectors = model.embed(
        ["Rotate production API credentials regularly.", "The cat sat on the mat."]
    )

    assert vectors[0] != pytest.approx(vectors[1], abs=1e-3)
