"""Paragraph-aware recursive character chunker.

See ingestion/protocols.py for the Chunker Protocol this implements. Character-based, not
token-based - a hand-rolled implementation with no tokenizer/framework dependency for now;
revisit if evaluation shows token-based chunking matters. Prefers to split on paragraph
boundaries, falling back to sentence and then word boundaries only when a unit doesn't fit in
one chunk on its own - a chunk is never split in the middle of a word.
"""

from __future__ import annotations

import re

from knowledge_assistant.ingestion.protocols import Chunker

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\s+")


class RecursiveCharacterChunker(Chunker):
    """Packs text into ~chunk_size-character windows with chunk_overlap characters shared
    between consecutive chunks."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be >= 0, got {chunk_overlap}")
        if chunk_overlap > chunk_size // 2:
            # A larger overlap silently multiplies chunk count (near one-word-per-chunk at the
            # extreme) with no error signal - fail fast instead, since chunk_overlap is a
            # first-class experimentation variable.
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must not exceed half of chunk_size "
                f"({chunk_size}), got chunk_size // 2 = {chunk_size // 2}"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        return self._pack(self._explode(text))

    def _explode(self, text: str) -> list[str]:
        """Breaks text into units that each fit in one chunk, splitting on the coarsest
        boundary that works (paragraph, then sentence, then word).

        shortcut: a single word longer than chunk_size is still kept whole (never split
        mid-word), so it may end up alone in a chunk that exceeds chunk_size. Upgrade path:
        add a hard character split for that pathological case if it ever shows up in real docs.
        """
        units: list[str] = []
        for paragraph in _PARAGRAPH_RE.split(text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) <= self.chunk_size:
                units.append(paragraph)
                continue
            for sentence in _SENTENCE_RE.split(paragraph):
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(sentence) <= self.chunk_size:
                    units.append(sentence)
                    continue
                units.extend(w for w in _WORD_RE.split(sentence) if w)
        return units

    def _pack(self, units: list[str]) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        i = 0
        while i < len(units):
            unit = units[i]
            added_len = len(unit) if not current else current_len + 1 + len(unit)
            if current and added_len > self.chunk_size:
                chunks.append(" ".join(current))
                seeded, seeded_len = self._seed_overlap(current)
                if seeded_len >= current_len:
                    # No overlap would fit without the unit still overflowing - drop it rather
                    # than looping forever re-packing the same units.
                    seeded, seeded_len = [], 0
                current, current_len = seeded, seeded_len
                continue
            current.append(unit)
            current_len = added_len
            i += 1

        if current:
            chunks.append(" ".join(current))
        return chunks

    def _seed_overlap(self, previous: list[str]) -> tuple[list[str], int]:
        """Starts the next chunk with trailing units from `previous` totalling roughly
        chunk_overlap characters, without splitting a unit."""
        if self.chunk_overlap <= 0:
            return [], 0
        seed: list[str] = []
        seed_len = 0
        for unit in reversed(previous):
            next_len = len(unit) if not seed else seed_len + 1 + len(unit)
            if seed and next_len > self.chunk_overlap:
                break
            seed.insert(0, unit)
            seed_len = next_len
        return seed, seed_len
