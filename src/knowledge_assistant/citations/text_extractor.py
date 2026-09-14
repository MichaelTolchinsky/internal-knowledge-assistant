"""Regex-based CitationExtractor: parses `(source: <document name>, chunk <chunk number>)`
markers out of the model's answer text - the exact format prompts/v1.py instructs the model to
produce.

See citations/protocols.py for the CitationExtractor Protocol this implements.
"""

from __future__ import annotations

import logging
import re

from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.domain import Answer, Citation, RetrievedChunk

logger = logging.getLogger(__name__)

# Tolerant of reasonable whitespace variation around the punctuation, but not engineered for
# formats the model was never instructed to produce (see prompts/v1.py's _INSTRUCTIONS).
_CITATION_MARKER_RE = re.compile(
    r"\(\s*source:\s*(?P<document_name>[^,()]+?)\s*,\s*chunk\s*(?P<chunk_index>\d+)\s*\)",
    re.IGNORECASE,
)

# Substrings of the exact abstention wording prompts/v1.py's _INSTRUCTIONS gives the model as
# its example phrasing ("I don't have enough information in the provided documents to answer
# this confidently"), covering the contraction and non-contraction spelling. Case-insensitive.
_ABSTENTION_PHRASES = (
    "don't have enough information in the provided documents",
    "do not have enough information in the provided documents",
)

# A citation's snippet is a preview for a UI/API response, not the full chunk - long enough to
# recognize which passage was used, short enough not to just re-dump settings.chunk_size worth
# of text (default 800 chars) into every citation.
_SNIPPET_MAX_CHARS = 200


class TextCitationExtractor(CitationExtractor):
    def extract(self, answer_text: str, chunks: list[RetrievedChunk]) -> Answer:
        citations = self._extract_citations(answer_text, chunks)
        abstained = self._is_abstained(answer_text)
        citations_missing = self._is_citations_missing(answer_text, citations, abstained)
        return Answer(
            text=answer_text,
            citations=citations,
            abstained=abstained,
            citations_missing=citations_missing,
        )

    def _extract_citations(self, answer_text: str, chunks: list[RetrievedChunk]) -> list[Citation]:
        chunks_by_key = {(chunk.document_name, chunk.chunk_index): chunk for chunk in chunks}

        citations: list[Citation] = []
        seen: set[tuple[str, int]] = set()
        for match in _CITATION_MARKER_RE.finditer(answer_text):
            document_name = match.group("document_name").strip()
            chunk_index = int(match.group("chunk_index"))
            key = (document_name, chunk_index)

            chunk = chunks_by_key.get(key)
            if chunk is None:
                logger.warning(
                    "Dropping hallucinated citation - no retrieved chunk matches "
                    "document_name=%r chunk_index=%d",
                    document_name,
                    chunk_index,
                )
                continue

            if key in seen:
                # The model cited the same source more than once (e.g. for two different
                # points) - one Citation per distinct source is enough, not one per mention.
                continue
            seen.add(key)

            citations.append(
                Citation(
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    chunk_index=chunk.chunk_index,
                    snippet=self._snippet(chunk.content),
                )
            )
        return citations

    @staticmethod
    def _snippet(content: str) -> str:
        if len(content) <= _SNIPPET_MAX_CHARS:
            return content
        return content[:_SNIPPET_MAX_CHARS].rstrip() + "..."

    @staticmethod
    def _is_abstained(answer_text: str) -> bool:
        """True only when the answer text matched the documented abstention phrase family -
        the model's explicit, actual signal that it doesn't have enough information. Deliberately
        does NOT consider citation presence - see _is_citations_missing for that separate signal
        (Step 9 fix-pass: collapsing both into one boolean corrupted abstention-accuracy and
        hallucination-count eval metrics, since three different outcomes all produced
        abstained=True for unrelated reasons)."""
        lowered = answer_text.lower()
        return any(phrase in lowered for phrase in _ABSTENTION_PHRASES)

    @staticmethod
    def _is_citations_missing(answer_text: str, citations: list[Citation], abstained: bool) -> bool:
        """True when the answer is non-empty, wasn't a documented abstention, and has zero
        valid citations. This is a citation-format-compliance signal, not a correctness
        judgment: in practice (see Step 9 fix-pass real end-to-end repro against the local
        model), this frequently fires for answers that are actually correct and grounded but
        where the model simply didn't include the "(source: ..., chunk N)" markers. Consumers
        (e.g. the eval runner or a future prompt-tuning pass) must not read
        citations_missing=True as "the answer is wrong" - it says nothing about correctness,
        only about whether citation markers were present."""
        return bool(answer_text.strip()) and not citations and not abstained
