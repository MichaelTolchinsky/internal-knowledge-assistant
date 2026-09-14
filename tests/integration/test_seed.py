"""Integration tests for ingest_directory (tests/integration/test_seed.py, per Step 15's scope):
multi-file ingestion, idempotency on a second run, and resilience to one malformed file not
aborting the rest of the directory. Real Postgres, real embedding model - no fakes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.dependencies import get_embedding_model
from knowledge_assistant.ingestion.service import ingest_directory

_DOC_A = """\
# Doc A

This is the first seed document, with enough real content across a couple of paragraphs that a
chunker would produce more than one chunk from it if it needed to.

A second paragraph, just so there is genuinely more than a single line of substance here.
"""

_DOC_B = """\
# Doc B

This is a second, different seed document - distinct content from Doc A, still with a couple of
real paragraphs of substance rather than a one-liner.

Another paragraph for Doc B, to keep it consistent with Doc A's shape.
"""


@pytest.fixture
def seed_dir(tmp_path: Path) -> Path:
    (tmp_path / "doc-a.md").write_bytes(_DOC_A.encode("utf-8"))
    (tmp_path / "doc-b.md").write_bytes(_DOC_B.encode("utf-8"))
    # A malformed file: invalid UTF-8 bytes, which TextParser/ParserError rejects (see
    # ingestion/parser.py) - this must not abort ingestion of doc-a.md/doc-b.md alongside it.
    (tmp_path / "broken.txt").write_bytes(b"\xff\xfe not valid utf-8 at all")
    return tmp_path


@pytest.mark.integration
async def test_ingest_directory_ingests_all_supported_files(
    seed_dir: Path, db_session: AsyncSession
) -> None:
    documents = await ingest_directory(seed_dir, db_session, get_embedding_model())

    names = {d.name for d in documents}
    assert names == {"doc-a.md", "doc-b.md"}


@pytest.mark.integration
async def test_ingest_directory_skips_already_ingested_content_on_second_run(
    seed_dir: Path, db_session: AsyncSession
) -> None:
    first_run = await ingest_directory(seed_dir, db_session, get_embedding_model())
    assert len(first_run) == 2

    second_run = await ingest_directory(seed_dir, db_session, get_embedding_model())

    assert second_run == []


@pytest.mark.integration
async def test_ingest_directory_does_not_crash_on_malformed_file(
    seed_dir: Path, db_session: AsyncSession
) -> None:
    """The malformed broken.txt must be logged and skipped, not raised - and the two valid
    files alongside it must still be ingested."""
    documents = await ingest_directory(seed_dir, db_session, get_embedding_model())

    names = {d.name for d in documents}
    assert "broken.txt" not in names
    assert names == {"doc-a.md", "doc-b.md"}
