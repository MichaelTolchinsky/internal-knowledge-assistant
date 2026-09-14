"""Evaluation runner: ingest seed docs (idempotent), run every dataset row through RAGService,
score with evaluation/metrics.py, and assemble an EvalReport.

No ingestion-service module exists yet (Step 15) - this reuses the same parse -> chunk -> embed
-> persist composition already proven in tests/integration/test_ingestion_flow.py, inline here,
rather than building new production ingestion code ahead of that step.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.config import settings
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
from knowledge_assistant.ingestion.chunker import RecursiveCharacterChunker
from knowledge_assistant.ingestion.parser import get_parser
from knowledge_assistant.rag_service import QueryTrace, RAGService
from knowledge_assistant.retrieval.pgvector import PgVectorRetriever
from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel

_DATASET_VERSION = "v1"


async def ingest_seed_docs(session: AsyncSession, seed_docs_dir: Path = SEED_DOCS_DIR) -> None:
    """Parses, chunks, and embeds every markdown file in seed_docs_dir and persists it as a
    Document + DocumentChunks - idempotent: a doc whose content_hash already exists is skipped
    entirely (not re-parsed/re-embedded/re-inserted), so running this repeatedly (e.g. once per
    eval run) never duplicates data or fails on the content_hash unique constraint."""
    embedder = get_embedding_model()
    chunker = RecursiveCharacterChunker(settings.chunk_size, settings.chunk_overlap)

    for path in sorted(seed_docs_dir.glob("*.md")):
        parsed = get_parser(path).parse(path)

        existing = await session.scalar(
            select(DocumentModel).where(DocumentModel.content_hash == parsed.content_hash)
        )
        if existing is not None:
            continue

        chunk_texts = chunker.chunk(parsed.text)
        embeddings = await embedder.embed(chunk_texts)

        document = DocumentModel(
            id=uuid.uuid4(), name=path.name, source=str(path), content_hash=parsed.content_hash
        )
        for index, (text, embedding) in enumerate(zip(chunk_texts, embeddings, strict=True)):
            document.chunks.append(
                DocumentChunkModel(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    chunk_index=index,
                    content=text,
                    embedding=embedding,
                )
            )
        session.add(document)

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
