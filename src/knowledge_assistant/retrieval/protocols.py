"""Retriever Protocol.

The Protocol lives in its own file, apart from concrete implementations, and every
implementation must explicitly subclass it.
"""

from __future__ import annotations

from typing import Protocol

from knowledge_assistant.domain import RetrievedChunk


class Retriever(Protocol):
    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        # Cosine similarity, range [-1, 1] - not a [0, 1] probability-like value.
        similarity_threshold: float | None = None,
    ) -> list[RetrievedChunk]: ...
