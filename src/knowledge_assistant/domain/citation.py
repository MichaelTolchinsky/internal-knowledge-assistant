"""Citation: a single source attribution backing part of an Answer."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Citation:
    document_id: UUID
    document_name: str
    chunk_index: int
    snippet: str
