"""RetrievedChunk: a DocumentChunk returned from vector search, with its similarity score.

Framework-free per docs/CODING-GUIDELINES.md section 5. Carries what a citation later needs
(FR3: document name, document id, chunk id, relevant text).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    document_name: str
    chunk_index: int
    content: str
    score: float  # cosine similarity, range [-1, 1] - not a [0, 1] probability-like value.
    metadata: dict[str, str] = field(default_factory=dict)
