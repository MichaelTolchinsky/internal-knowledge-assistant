"""Unit tests for TextCitationExtractor (tests/unit - pure function, no DB/network)."""

from __future__ import annotations

import logging
import uuid

import pytest

from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.citations.text_extractor import TextCitationExtractor
from knowledge_assistant.domain import RetrievedChunk


def _chunk(
    document_name: str, chunk_index: int, content: str, score: float = 0.9
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name=document_name,
        chunk_index=chunk_index,
        content=content,
        score=score,
    )


@pytest.mark.unit
def test_text_citation_extractor_subclasses_protocol() -> None:
    # `issubclass()` against a plain (non-@runtime_checkable) Protocol always raises, even for
    # real nominal inheritance - checking the MRO directly confirms explicit subclassing
    # without needing to make the Protocol runtime-checkable just for this test.
    assert CitationExtractor in TextCitationExtractor.__mro__


@pytest.mark.unit
def test_single_citation_matched_to_real_chunk() -> None:
    chunk = _chunk("rate-limits.md", 2, "The default rate limit is 100 requests per minute.")
    answer_text = (
        "The default rate limit is 100 requests per minute (source: rate-limits.md, chunk 2)."
    )

    answer = TextCitationExtractor().extract(answer_text, [chunk])

    assert len(answer.citations) == 1
    citation = answer.citations[0]
    assert citation.document_id == chunk.document_id
    assert citation.document_name == "rate-limits.md"
    assert citation.chunk_index == 2
    assert citation.snippet == chunk.content
    assert answer.text == answer_text
    assert answer.abstained is False
    assert answer.citations_missing is False


@pytest.mark.unit
def test_multiple_citations_all_matched_no_drops_or_duplicates() -> None:
    chunk_a = _chunk("rate-limits.md", 2, "The default rate limit is 100 requests per minute.")
    chunk_b = _chunk("auth.md", 0, "Rotate API credentials every 90 days.")
    answer_text = (
        "The rate limit is 100 req/min (source: rate-limits.md, chunk 2). "
        "Rotate credentials every 90 days (source: auth.md, chunk 0)."
    )

    answer = TextCitationExtractor().extract(answer_text, [chunk_a, chunk_b])

    keys = {(c.document_name, c.chunk_index) for c in answer.citations}
    assert keys == {("rate-limits.md", 2), ("auth.md", 0)}
    assert len(answer.citations) == 2


@pytest.mark.unit
def test_repeated_citation_of_same_source_is_not_duplicated() -> None:
    chunk = _chunk("auth.md", 0, "Rotate API credentials every 90 days.")
    answer_text = (
        "Rotate credentials every 90 days (source: auth.md, chunk 0). "
        "This applies to all keys (source: auth.md, chunk 0)."
    )

    answer = TextCitationExtractor().extract(answer_text, [chunk])

    assert len(answer.citations) == 1


@pytest.mark.unit
def test_citation_naming_unretrieved_chunk_is_dropped_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    chunk = _chunk("auth.md", 0, "Rotate API credentials every 90 days.")
    answer_text = "Rotate credentials every 90 days (source: nonexistent-doc.md, chunk 99)."

    with caplog.at_level(logging.WARNING):
        answer = TextCitationExtractor().extract(answer_text, [chunk])

    assert answer.citations == []
    assert any("nonexistent-doc.md" in record.getMessage() for record in caplog.records)


@pytest.mark.unit
def test_abstention_phrase_sets_abstained_true() -> None:
    answer_text = (
        "I don't have enough information in the provided documents to answer this confidently."
    )

    answer = TextCitationExtractor().extract(answer_text, [])

    assert answer.abstained is True
    assert answer.citations_missing is False


@pytest.mark.unit
def test_non_contraction_abstention_phrase_also_detected() -> None:
    answer_text = (
        "I do not have enough information in the provided documents to answer this confidently."
    )

    answer = TextCitationExtractor().extract(answer_text, [])

    assert answer.abstained is True
    assert answer.citations_missing is False


@pytest.mark.unit
def test_normal_answer_with_valid_citations_is_not_abstained_and_not_missing_citations() -> None:
    chunk = _chunk("rate-limits.md", 2, "The default rate limit is 100 requests per minute.")
    answer_text = "The rate limit is 100 req/min (source: rate-limits.md, chunk 2)."

    answer = TextCitationExtractor().extract(answer_text, [chunk])

    assert answer.abstained is False
    assert answer.citations_missing is False


@pytest.mark.unit
def test_zero_citations_non_empty_answer_sets_citations_missing_not_abstained() -> None:
    """A non-empty answer with no valid citations and no abstention phrase match is neither a
    documented abstention nor silently ignored - it sets citations_missing=True,
    abstained=False. Known tradeoff, documented deliberately: this also fires for a model that
    gave a genuinely correct, grounded answer but simply forgot to add citation markers (a
    formatting slip, not an abstention or a wrong answer) - citations_missing is a
    citation-format-compliance signal, not a correctness judgment, and must not be misread as
    "the answer is wrong."
    """
    answer_text = "The rate limit is 100 requests per minute."

    answer = TextCitationExtractor().extract(answer_text, [])

    assert answer.citations == []
    assert answer.abstained is False
    assert answer.citations_missing is True


@pytest.mark.unit
def test_citation_snippet_is_truncated_for_long_content() -> None:
    long_content = "x" * 250
    chunk = _chunk("long-doc.md", 0, long_content)
    answer_text = "See details (source: long-doc.md, chunk 0)."

    answer = TextCitationExtractor().extract(answer_text, [chunk])

    snippet = answer.citations[0].snippet
    assert snippet != long_content
    assert snippet.endswith("...")
    assert len(snippet) < len(long_content)
    assert snippet[:-3] == long_content[: len(snippet) - 3]
