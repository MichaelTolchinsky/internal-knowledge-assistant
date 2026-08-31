"""Unit tests for the recursive character chunker (tests/unit - pure function, no I/O)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from knowledge_assistant.ingestion.chunker import RecursiveCharacterChunker


@pytest.mark.unit
def test_rejects_chunk_overlap_too_large_relative_to_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RecursiveCharacterChunker(chunk_size=50, chunk_overlap=45)


@pytest.mark.unit
def test_rejects_non_positive_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        RecursiveCharacterChunker(chunk_size=0, chunk_overlap=0)


@pytest.mark.unit
def test_rejects_negative_chunk_overlap() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RecursiveCharacterChunker(chunk_size=50, chunk_overlap=-1)


@pytest.mark.unit
def test_empty_string_returns_empty_list() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=20)

    assert chunker.chunk("") == []
    assert chunker.chunk("   \n\n  ") == []


@pytest.mark.unit
def test_short_document_returns_one_chunk() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=20)
    text = "A short paragraph that easily fits in a single chunk."

    chunks = chunker.chunk(text)

    assert chunks == [text]


@pytest.mark.unit
def test_never_splits_mid_word() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=20, chunk_overlap=5)
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    text = " ".join(words)

    chunks = chunker.chunk(text)

    for chunk in chunks:
        for token in chunk.split():
            assert token in words


@pytest.mark.unit
def test_respects_chunk_size_budget() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=10)
    paragraph = " ".join(f"word{i}" for i in range(60))

    chunks = chunker.chunk(paragraph)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50


@pytest.mark.unit
def test_consecutive_chunks_overlap_by_roughly_configured_amount() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=50, chunk_overlap=15)
    paragraph = " ".join(f"word{i}" for i in range(60))

    chunks = chunker.chunk(paragraph)

    assert len(chunks) > 1
    for first, second in pairwise(chunks):
        first_words = first.split()
        second_words = second.split()
        # The last word of `first` must reappear near the start of `second` - proof the
        # configured overlap actually carried words across the chunk boundary.
        assert first_words[-1] in second_words


@pytest.mark.unit
def test_splits_on_paragraph_boundaries_when_possible() -> None:
    chunker = RecursiveCharacterChunker(chunk_size=40, chunk_overlap=0)
    text = "First paragraph is short.\n\nSecond paragraph is also short."

    chunks = chunker.chunk(text)

    assert "First paragraph is short." in chunks
    assert "Second paragraph is also short." in chunks
