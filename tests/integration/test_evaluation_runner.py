"""Integration tests for the evaluation runner's mechanics (real Postgres, real embedding
model, real local LLM - same "prove it actually works" philosophy as the rest of
tests/integration/). Deliberately does NOT run the full 57-question dataset here (too slow for
routine testing) - only a tiny slice, to verify ingestion + scoring + report assembly actually
work end-to-end. The real full-dataset run is a manual, on-demand step (see
src/knowledge_assistant/evaluation/runner.py's `main()`), not part of the automated suite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.dependencies import (
    get_citation_extractor,
    get_embedding_model,
    get_llm_client_singleton,
    get_prompt_builder,
)
from knowledge_assistant.evaluation.dataset_loader import load_dataset
from knowledge_assistant.evaluation.runner import ingest_seed_docs, run_evaluation
from knowledge_assistant.rag_service import RAGService
from knowledge_assistant.retrieval.pgvector import PgVectorRetriever
from knowledge_assistant.storage.models import DocumentModel


async def _document_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(DocumentModel))


@pytest.mark.integration
async def test_ingest_seed_docs_persists_all_seed_documents(db_session: AsyncSession) -> None:
    await ingest_seed_docs(db_session)

    count = await _document_count(db_session)
    # evaluation/seed_docs/ currently has 11 files - assert a lower bound so this test
    # doesn't need updating every time a seed doc is added, only if the directory goes empty.
    assert count >= 8


@pytest.mark.integration
async def test_ingest_seed_docs_is_idempotent(db_session: AsyncSession) -> None:
    await ingest_seed_docs(db_session)
    first_count = await _document_count(db_session)

    await ingest_seed_docs(db_session)
    second_count = await _document_count(db_session)

    assert second_count == first_count


@pytest.mark.integration
async def test_run_evaluation_scores_a_small_subset_with_real_numbers(
    db_session: AsyncSession,
) -> None:
    await ingest_seed_docs(db_session)

    rag_service = RAGService(
        embedding_model=get_embedding_model(),
        retriever=PgVectorRetriever(db_session),
        prompt_builder=get_prompt_builder(),
        llm_client=get_llm_client_singleton(),
        citation_extractor=get_citation_extractor(),
    )

    full_dataset = load_dataset()
    # Deliberately mixed: at least one answerable and one unanswerable row, so both branches of
    # _score_row are exercised, not just one.
    subset = [r for r in full_dataset if r.category == "answerable"][:2] + [
        r for r in full_dataset if r.category == "unanswerable"
    ][:2]
    assert len(subset) == 4

    report = await run_evaluation(db_session, rag_service, subset)

    assert report.num_questions == 4
    assert report.num_answerable == 2
    assert report.num_unanswerable == 2
    assert len(report.row_results) == 4

    for result in report.row_results:
        if result.row.category == "answerable":
            assert result.correctness in (True, False)
            assert result.retrieval_hit in (True, False)
            assert result.grounded in (True, False)
            assert result.abstention_correct is None
        else:
            assert result.abstention_correct in (True, False)
            assert result.correctness is None

        # Real numbers, not stubbed zeros: every row actually went through the real LLM.
        assert result.trace.total_latency_ms > 0
        assert result.trace.llm_response.output_tokens > 0

    assert 0.0 <= report.answer_correctness_pct <= 100.0
    assert 0.0 <= report.recall_at_k_pct <= 100.0
    assert 0.0 <= report.groundedness_pct <= 100.0
    assert 0.0 <= report.abstention_accuracy_pct <= 100.0
    assert report.avg_total_latency_ms > 0
    assert report.total_input_tokens > 0
    assert report.total_output_tokens > 0
