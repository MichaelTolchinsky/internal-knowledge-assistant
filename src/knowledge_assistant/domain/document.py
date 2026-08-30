"""Document: a single ingested source document (before chunking).

Framework-free per docs/CODING-GUIDELINES.md section 5 - no FastAPI/SQLAlchemy dependency here,
so core RAG logic can be tested without the API or DB layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    name: str
    source: str
    content_hash: str
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
