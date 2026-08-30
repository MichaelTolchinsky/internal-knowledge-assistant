import uuid
from datetime import UTC, datetime

import pytest

from knowledge_assistant.domain import Document, DocumentChunk


@pytest.mark.unit
def test_document_defaults_to_empty_metadata() -> None:
    doc = Document(
        id=uuid.uuid4(),
        name="api-security.md",
        source="docs/api-security.md",
        content_hash="abc123",
    )

    assert doc.metadata == {}
    assert doc.created_at is None


@pytest.mark.unit
def test_document_is_immutable() -> None:
    doc = Document(id=uuid.uuid4(), name="a.md", source="docs/a.md", content_hash="abc123")

    with pytest.raises(AttributeError):
        doc.name = "b.md"  # type: ignore[misc]


@pytest.mark.unit
def test_document_chunk_holds_optional_embedding() -> None:
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        content="Rotate production API credentials by...",
        created_at=datetime.now(UTC),
    )

    assert chunk.embedding is None
    assert chunk.chunk_index == 0
