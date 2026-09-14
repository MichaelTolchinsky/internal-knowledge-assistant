"""Evaluation runner: ingest seed docs (idempotent), run every dataset row through RAGService,
score with evaluation/metrics.py, and assemble an EvalReport.

Ingestion itself is not implemented here - it delegates to ingestion/service.py, shared with
the seed CLI (seed/seed.py) and tests/integration/test_ingestion_flow.py, rather than
maintaining its own copy of the parse -> chunk -> embed -> persist logic.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.dependencies import (
    get_citation_extractor,
    get_embedding_model,
    get_llm_client_singleton,
    get_prompt_builder,
)
from knowledge_assistant.evaluation import metrics
from knowledge_assistant.evaluation.dataset_loader import (
    DEFAULT_DATASET_PATH,
    SEED_DOCS_DIR,
    EvalRow,
    load_dataset,
)
from knowledge_assistant.evaluation.report import EvalReport, RowResult, build_report
from knowledge_assistant.ingestion.service import ingest_directory
from knowledge_assistant.rag_service import QueryTrace, RAGService
from knowledge_assistant.retrieval.pgvector import PgVectorRetriever

_DATASET_VERSION = "v1"


async def ingest_seed_docs(session: AsyncSession, seed_docs_dir: Path = SEED_DOCS_DIR) -> None:
    """Ingests every supported file in seed_docs_dir - idempotent (a doc whose content_hash
    already exists is skipped entirely), so running this repeatedly (e.g. once per eval run)
    never duplicates data or fails on the content_hash unique constraint. Thin wrapper around
    ingestion/service.py's ingest_directory, kept as a separate name/signature here since
    existing callers (this module's _main(), tests/integration/test_evaluation_runner.py)
    already depend on it and don't need ingest_directory's richer return value."""
    await ingest_directory(seed_docs_dir, session, get_embedding_model())
    await session.commit()


def _score_row(row: EvalRow, trace: QueryTrace) -> RowResult:
    if row.category == "answerable":
        return RowResult(
            row=row,
            trace=trace,
            correctness=metrics.answer_correctness(trace.answer.text, row.expected_answer),
            retrieval_hit=metrics.retrieval_hit(trace.chunks, row.expected_sources),
            grounded=metrics.groundedness(trace.answer, row.expected_sources),
            abstention_correct=None,
        )
    return RowResult(
        row=row,
        trace=trace,
        correctness=None,
        retrieval_hit=None,
        grounded=None,
        abstention_correct=metrics.abstention_correct(row, trace.answer),
    )


async def run_evaluation(
    session: AsyncSession, rag_service: RAGService, dataset: list[EvalRow]
) -> EvalReport:
    """Runs every row in `dataset` through `rag_service`, scores each, and returns the
    aggregate report. Does not ingest anything - call ingest_seed_docs first."""
    row_results = []
    for row in dataset:
        trace = await rag_service.answer_question_with_trace(row.question)
        row_results.append(_score_row(row, trace))

    return build_report(_DATASET_VERSION, row_results)


async def _main() -> None:
    from knowledge_assistant.evaluation.report import render_markdown, render_summary
    from knowledge_assistant.storage.database import async_session_factory

    async with async_session_factory() as session:
        print(f"Ingesting seed docs from {SEED_DOCS_DIR} ...")
        await ingest_seed_docs(session)

        rag_service = RAGService(
            embedding_model=get_embedding_model(),
            retriever=PgVectorRetriever(session),
            prompt_builder=get_prompt_builder(),
            llm_client=get_llm_client_singleton(),
            citation_extractor=get_citation_extractor(),
        )

        dataset = load_dataset(DEFAULT_DATASET_PATH)
        print(f"Running {len(dataset)} questions from {DEFAULT_DATASET_PATH} ...")
        report = await run_evaluation(session, rag_service, dataset)

    print()
    print(render_summary(report))

    reports_dir = DEFAULT_DATASET_PATH.parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{report.run_at.replace(':', '-')}-{_DATASET_VERSION}.md"
    report_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"\nFull report written to {report_path}")


def main() -> None:
    """CLI entry point: `python -m knowledge_assistant.evaluation.runner`. Manual/on-demand only
    - requires real Postgres + downloads/runs real local models, too slow/expensive to run on
    every commit (see tests/integration/test_evaluation_runner.py for the fast, small-subset
    mechanics test that does run in CI)."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
