import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel


@pytest.mark.integration
async def test_can_persist_document_with_chunk_and_embedding(db_session: AsyncSession) -> None:
    document = DocumentModel(
        id=uuid.uuid4(),
        name="api-security.md",
        source="docs/api-security.md",
        content_hash=f"hash-{uuid.uuid4()}",
    )
    chunk = DocumentChunkModel(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Rotate production API credentials by...",
        embedding=[0.1] * 384,
    )
    document.chunks.append(chunk)

    db_session.add(document)
    await db_session.commit()

    result = await db_session.execute(
        select(DocumentModel)
        .options(selectinload(DocumentModel.chunks))
        .where(DocumentModel.id == document.id)
    )
    persisted = result.scalar_one()

    assert persisted.content_hash == document.content_hash
    assert len(persisted.chunks) == 1
    assert persisted.chunks[0].embedding is not None
    assert len(persisted.chunks[0].embedding) == 384
