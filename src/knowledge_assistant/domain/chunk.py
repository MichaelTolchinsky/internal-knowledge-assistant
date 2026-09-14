"""DocumentChunk: one chunk of a Document, with its embedding."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: datetime | None = None
