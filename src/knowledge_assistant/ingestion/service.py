"""Shared ingestion logic: parse -> chunk -> embed -> persist as Document + DocumentChunk rows.
Used by both the seed CLI (seed/seed.py) and the evaluation runner (evaluation/runner.py) - one
implementation, not one copy per caller.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.config import settings
from knowledge_assistant.domain import Document
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.ingestion.chunker import RecursiveCharacterChunker
from knowledge_assistant.ingestion.parser import ParserError, get_parser
from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel

logger = logging.getLogger(__name__)

# Matches ingestion/parser.py's own dispatch dict - kept in sync manually since parser.py
# doesn't expose its suffix set publicly (a small, stable list, not worth adding an accessor
# for yet). Public (not underscore-prefixed) so other callers - e.g. seed/seed.py's own
# pre-count of "files considered" - can import it instead of duplicating the list.
SUPPORTED_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".pdf"})


def _to_domain(document_model: DocumentModel) -> Document:
    return Document(
        id=document_model.id,
        name=document_model.name,
        source=document_model.source,
        content_hash=document_model.content_hash,
        metadata=document_model.metadata_,
        created_at=document_model.created_at,
        updated_at=document_model.updated_at,
    )


async def ingest_document(
    path: Path, session: AsyncSession, embedding_model: EmbeddingModel
) -> Document | None:
    """Parses, chunks, and embeds one file and persists it as a Document + DocumentChunks.

    Idempotent: if a Document with this content's exact sha256 hash already exists, this is a
    no-op that returns None ("content_hash is the natural dedupe key" for repeatable
    ingestion) - it does not re-parse, re-embed, or attempt a duplicate insert.

    Flushes (not commits) after inserting, so a duplicate-content check later in the same
    session/transaction (e.g. another file in the same ingest_directory call, or a caller
    checking before its own commit) sees this row. Committing is the caller's decision, not
    this function's - see ingest_directory and seed/seed.py for where that happens.

    Raises ParserError (unchanged, not swallowed here) if the file can't be parsed - the caller
    decides whether that should stop the whole run or be logged and skipped (see
    ingest_directory, which does the latter).
    """
    parsed = get_parser(path).parse(path)

    existing = await session.scalar(
        select(DocumentModel).where(DocumentModel.content_hash == parsed.content_hash)
    )
    if existing is not None:
        return None

    chunker = RecursiveCharacterChunker(settings.chunk_size, settings.chunk_overlap)
    chunk_texts = chunker.chunk(parsed.text)
    embeddings = await embedding_model.embed(chunk_texts)

    document_model = DocumentModel(
        id=uuid.uuid4(), name=path.name, source=str(path), content_hash=parsed.content_hash
    )
    for index, (text, embedding) in enumerate(zip(chunk_texts, embeddings, strict=True)):
        document_model.chunks.append(
            DocumentChunkModel(
                id=uuid.uuid4(),
                document_id=document_model.id,
                chunk_index=index,
                content=text,
                embedding=embedding,
            )
        )
    session.add(document_model)
    await session.flush()

    return _to_domain(document_model)


async def ingest_directory(
    dir_path: Path, session: AsyncSession, embedding_model: EmbeddingModel
) -> list[Document]:
    """Ingests every supported file (.md, .markdown, .txt, .pdf) directly under dir_path, in
    sorted order, via ingest_document. Returns only the newly-ingested Documents - files
    skipped because their content_hash already exists are not included (see ingest_document).

    Resilient by design: a file that fails to parse (ParserError) is logged as a warning and
    skipped, not raised - one bad file must not abort ingestion of the rest of the directory.
    Callers that want the per-file skip/error detail (e.g. seed/seed.py's human-readable
    summary) should configure logging to see these INFO/WARNING lines; this function's return
    value only reports the successfully-ingested set, per its stated contract.
    """
    documents: list[Document] = []
    for path in sorted(dir_path.iterdir()):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue

        try:
            document = await ingest_document(path, session, embedding_model)
        except ParserError:
            logger.warning("Skipping %s - failed to parse", path, exc_info=True)
            continue

        if document is None:
            logger.info("Skipping %s - already ingested (content_hash matches)", path)
            continue

        logger.info("Ingested %s as document %s", path, document.id)
        documents.append(document)

    return documents
