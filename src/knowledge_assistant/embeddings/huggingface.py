"""HuggingFace/sentence-transformers embedding model.

See embeddings/protocols.py for the EmbeddingModel Protocol this implements.
"""

from __future__ import annotations

import asyncio

from sentence_transformers import SentenceTransformer

from knowledge_assistant.config import settings
from knowledge_assistant.embeddings.protocols import EmbeddingModel


class EmbeddingDimensionMismatchError(Exception):
    """Raised when the loaded model's actual output dimension doesn't match
    settings.embedding_dimension - a silent mismatch here would corrupt the pgvector(384)
    column (see docs/ARCHITECTURE.md section 4 / Open Decisions)."""


class HuggingFaceEmbeddingModel(EmbeddingModel):
    """Loads a sentence-transformers model once at construction time (model load is the
    expensive part - never reload per call) and embeds text into plain Python float lists,
    since that's what the pgvector/SQLAlchemy `Vector` column type expects, not numpy arrays.

    `embed()` is declared `async` to match the EmbeddingModel Protocol - following the same
    pattern as `LocalLLMClient.generate()` in llm/local.py: `sentence-transformers`' underlying
    `.encode()` call is CPU-bound, not I/O-bound, so there's no event loop to cooperate with
    during inference. Rather than block the event loop for the whole call, the actual blocking
    work is offloaded to a worker thread via `asyncio.to_thread`, so callers get a consistent
    async interface without needing to think about threading themselves (see
    docs/ARCHITECTURE.md Open Decisions for why `asyncio.to_thread` and not
    `ProcessPoolExecutor` - PyTorch releases the GIL during tensor computation, so this still
    gets genuine cross-core concurrency).
    """

    def __init__(self, model_name: str | None = None) -> None:
        resolved_model_name = model_name or settings.embedding_model_name
        self._model = SentenceTransformer(resolved_model_name)

        actual_dimension = self._model.get_embedding_dimension()
        if actual_dimension != settings.embedding_dimension:
            raise EmbeddingDimensionMismatchError(
                f"Model {resolved_model_name!r} outputs {actual_dimension}-dim vectors, but "
                f"settings.embedding_dimension is {settings.embedding_dimension}. The "
                f"pgvector column is fixed at settings.embedding_dimension - update it (and "
                f"migrate + re-embed) before switching models."
            )
        self.dimension = actual_dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [vector.tolist() for vector in embeddings]
