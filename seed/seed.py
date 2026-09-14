"""Seed CLI: (re-)populate the local knowledge base from a directory of documents.

Deterministic, repeatable, safely re-runnable: recreates the local knowledge base from the
source directory every time, idempotent per content_hash (see
knowledge_assistant.ingestion.service.ingest_directory) - re-running never duplicates data.

Layout note: this is a plain top-level script under seed/, not a module inside the
src/knowledge_assistant/ package (unlike evaluation/runner.py's `python -m
knowledge_assistant.evaluation.runner` entry point) - matching the repo layout convention that
already anticipated `seed/` as a top-level directory (like `docker/`, `evaluation/`), not a
package. It still follows the same shape as the eval runner's CLI (a `main()` + `if __name__ ==
"__main__":` guard, plain `print()` for human-facing output, real Postgres + real embedding
model - not something that runs in CI automatically).

No seed/documents/ directory: this project's only real document corpus is
evaluation/seed_docs/ (created for the evaluation dataset). Duplicating that content into
a second seed/documents/ directory would create two copies of "the same 11 docs" that could
silently drift apart - one directory in a fast-moving repo staying in sync is enough. This
script instead defaults its source directory to evaluation/seed_docs/, and takes a --source-dir
argument (or SEED_SOURCE_DIR env var) so a real, separate seed corpus can be pointed at later
without needing this script rewritten.

Usage:
    python seed/seed.py                       # ingests evaluation/seed_docs/ (default)
    python seed/seed.py --source-dir path/to/docs
    SEED_SOURCE_DIR=path/to/docs python seed/seed.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from pathlib import Path

from sqlalchemy import func, select

from knowledge_assistant.dependencies import get_embedding_model
from knowledge_assistant.evaluation.dataset_loader import SEED_DOCS_DIR
from knowledge_assistant.ingestion.service import SUPPORTED_SUFFIXES, ingest_directory
from knowledge_assistant.storage.database import async_session_factory
from knowledge_assistant.storage.models import DocumentChunkModel


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(os.environ.get("SEED_SOURCE_DIR", str(SEED_DOCS_DIR))),
        help=f"Directory of documents to ingest (default: {SEED_DOCS_DIR}, "
        "or $SEED_SOURCE_DIR if set)",
    )
    return parser.parse_args()


async def _run(source_dir: Path) -> None:
    considered = [p for p in sorted(source_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    print(f"Seeding from {source_dir} ({len(considered)} supported files found) ...")

    async with async_session_factory() as session:
        embedding_model = get_embedding_model()
        new_documents = await ingest_directory(source_dir, session, embedding_model)
        await session.commit()

        new_chunk_count = 0
        if new_documents:
            new_chunk_count = await session.scalar(
                select(func.count())
                .select_from(DocumentChunkModel)
                .where(DocumentChunkModel.document_id.in_([d.id for d in new_documents]))
            )

    # ingest_directory's return value only reports what's newly ingested (its documented
    # contract) - it doesn't separately report "skipped because already present" vs. "skipped
    # because it failed to parse" for this summary, so both fall under "not newly ingested"
    # here; the per-file INFO/WARNING log lines above (from ingest_directory itself) show the
    # actual breakdown.
    not_newly_ingested = len(considered) - len(new_documents)

    print()
    print("Seed summary:")
    print(f"  files considered:      {len(considered)}")
    print(f"  newly ingested:        {len(new_documents)} ({new_chunk_count} chunks)")
    print(f"  already present/error: {not_newly_ingested}")
    if new_documents:
        print("\n  New documents:")
        for document in new_documents:
            print(f"    - {document.name} ({document.id})")
    print(
        "\n(See log output above for the per-file breakdown of what was skipped as "
        "already-present vs. failed to parse.)"
    )


def main() -> None:
    """CLI entry point: `python seed/seed.py [--source-dir PATH]`. Manual/on-demand, same
    philosophy as evaluation/runner.py's CLI - requires real Postgres + downloads/runs the real
    embedding model, not something CI runs on every commit."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()
    asyncio.run(_run(args.source_dir))


if __name__ == "__main__":
    main()
