"""Unit tests for evaluation/metrics.py - pure functions, constructed fixtures, no DB/model."""

from __future__ import annotations

import uuid

import pytest

from knowledge_assistant.domain import Answer, Citation, RetrievedChunk
from knowledge_assistant.evaluation import metrics
from knowledge_assistant.evaluation.dataset_loader import EvalRow


def _chunk(document_name: str, chunk_index: int = 0, score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        chunk_index=chunk_index,
        content="irrelevant for this metric",
        score=score,
    )


def _citation(document_name: str, chunk_index: int = 0) -> Citation:
    return Citation(
        document_id=uuid.uuid4(),
        document_name=document_name,
        chunk_index=chunk_index,
        snippet="irrelevant for this metric",
    )


@pytest.mark.unit
def test_answer_correctness_true_for_high_word_overlap() -> None:
    assert metrics.answer_correctness(
        "The default API rate limit is 100 requests per minute per API key.",
        "100 requests per minute per API key.",
    )


@pytest.mark.unit
def test_answer_correctness_false_for_unrelated_answer() -> None:
    assert not metrics.answer_correctness(
        "Rotate your credentials every 90 days.",
        "100 requests per minute per API key.",
    )


@pytest.mark.unit
def test_answer_correctness_true_for_nonempty_answer_against_empty_expected() -> None:
    assert metrics.answer_correctness("some answer", "   ")


@pytest.mark.unit
def test_retrieval_hit_true_when_expected_source_is_among_retrieved_chunks() -> None:
    chunks = [_chunk("rate-limits.md"), _chunk("auth.md")]
    assert metrics.retrieval_hit(chunks, ["auth.md"])


@pytest.mark.unit
def test_retrieval_hit_false_when_expected_source_not_retrieved() -> None:
    chunks = [_chunk("rate-limits.md")]
    assert not metrics.retrieval_hit(chunks, ["auth.md"])


@pytest.mark.unit
def test_retrieval_hit_true_when_no_expected_sources() -> None:
    # No expected_sources means nothing to check for - vacuously true, not a failure.
    assert metrics.retrieval_hit([], [])


@pytest.mark.unit
def test_groundedness_true_when_citation_matches_expected_source() -> None:
    answer = Answer(text="...", citations=[_citation("rate-limits.md")])
    assert metrics.groundedness(answer, ["rate-limits.md"])


@pytest.mark.unit
def test_groundedness_false_when_citation_points_elsewhere() -> None:
    answer = Answer(text="...", citations=[_citation("auth.md")])
    assert not metrics.groundedness(answer, ["rate-limits.md"])


@pytest.mark.unit
def test_groundedness_false_when_no_citations_even_if_correct_text() -> None:
    answer = Answer(text="a correct-sounding but uncited answer", citations=[])
    assert not metrics.groundedness(answer, ["rate-limits.md"])


@pytest.mark.unit
def test_abstention_correct_true_when_abstained() -> None:
    row = EvalRow(
        id="q1",
        question="?",
        category="unanswerable",
        expected_answer="ABSTAIN",
        expected_sources=[],
    )
    answer = Answer(text="I don't know", abstained=True, citations_missing=False)
    assert metrics.abstention_correct(row, answer)


@pytest.mark.unit
def test_abstention_correct_true_when_citations_missing_but_not_abstained() -> None:
    row = EvalRow(
        id="q1",
        question="?",
        category="unanswerable",
        expected_answer="ABSTAIN",
        expected_sources=[],
    )
    answer = Answer(text="some ungrounded guess", abstained=False, citations_missing=True)
    assert metrics.abstention_correct(row, answer)


@pytest.mark.unit
def test_abstention_correct_false_when_neither_signal_fires() -> None:
    row = EvalRow(
        id="q1",
        question="?",
        category="unanswerable",
        expected_answer="ABSTAIN",
        expected_sources=[],
    )
    answer = Answer(
        text="confidently wrong",
        citations=[_citation("some-doc.md")],
        abstained=False,
        citations_missing=False,
    )
    assert not metrics.abstention_correct(row, answer)
