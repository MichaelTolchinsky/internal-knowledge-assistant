"""EmbeddingModel Protocol.

Per docs/CODING-GUIDELINES.md section 3/4: the Protocol lives in its own file, apart from
concrete implementations, and every implementation must explicitly subclass it.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingModel(Protocol):
    """Turns text into a fixed-dimension vector. Query and document text must use the same
    implementation/model so vectors are comparable."""

    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
