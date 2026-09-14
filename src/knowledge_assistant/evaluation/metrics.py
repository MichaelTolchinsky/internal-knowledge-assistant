"""Evaluation metrics per docs/ARCHITECTURE.md section 3.3 (answer correctness, Recall@K,
groundedness, abstention accuracy, latency, cost).

This is a learning project, not a production eval harness - scoring is deliberately simple and
explainable, not semantic-similarity scoring or an LLM-judge (both reasonable future upgrades,
out of scope now). Each function below documents exactly what it checks and its known
limitations, so results are interpretable rather than a black-box score.
"""

from __future__ import annotations

import re

from knowledge_assistant.domain import Answer, RetrievedChunk
from knowledge_assistant.evaluation.dataset_loader import EvalRow

# A small stopword list - just enough to stop common connective words from diluting the overlap
# ratio. Not a linguistically complete stopword list (that would be over-engineering for a
# simple heuristic check).
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "and",
        "or",
        "but",
        "not",
        "no",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "their",
        "there",
        "here",
        "what",
        "which",
        "who",
        "how",
        "when",
        "where",
        "why",
        "can",
        "could",
        "should",
        "would",
        "will",
        "shall",
        "may",
        "might",
        "must",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "if",
        "then",
        "than",
        "so",
    ]
)

_WORD_RE = re.compile(r"[a-z0-9]+")

# Correct if at least this fraction of expected_answer's significant words show up in the
# generated answer. 0.5 chosen as a middle ground: strict enough to catch answers that miss
# most of the expected facts, loose enough to tolerate paraphrasing/reordering - not tuned
# against labeled data, just a reasonable starting point for this heuristic.
_CORRECTNESS_OVERLAP_THRESHOLD = 0.5


def _significant_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def answer_correctness(generated_answer: str, expected_answer: str) -> bool:
    """Simple keyword/fact-overlap heuristic, NOT semantic similarity or an LLM-judge: extracts
    the significant (non-stopword) words from expected_answer and checks what fraction of them
    literally appear in generated_answer. Correct if that fraction is >= 0.5.

    Known limitations: a correct answer phrased with entirely different vocabulary (e.g. "429"
    vs "too many requests") can score as incorrect; an answer that repeats expected_answer's
    key nouns without actually answering the question can score as correct. Good enough to spot
    large regressions/improvements across eval runs, not precise enough to trust a single
    borderline score.
    """
    expected_words = _significant_words(expected_answer)
    if not expected_words:
        return bool(generated_answer.strip())
    generated_words = _significant_words(generated_answer)
    overlap = expected_words & generated_words
    return (len(overlap) / len(expected_words)) >= _CORRECTNESS_OVERLAP_THRESHOLD


def retrieval_hit(chunks: list[RetrievedChunk], expected_sources: list[str]) -> bool:
    """Recall@K / source hit rate: did the top-K retrieved chunks include at least one chunk
    from an expected source document? (Not per-chunk precision - just "was the right document
    in the retrieved set at all".)"""
    if not expected_sources:
        return True
    retrieved_names = {chunk.document_name for chunk in chunks}
    return any(source in retrieved_names for source in expected_sources)


def groundedness(answer: Answer, expected_sources: list[str]) -> bool:
    """Did the answer's citations actually reference the expected source document?

    TextCitationExtractor (Step 9) already drops any citation marker that doesn't match a real
    retrieved chunk - so every Citation in answer.citations is, by construction, non-hallucinated
    (it necessarily points at a chunk that was genuinely retrieved). This metric checks one
    level further: not just "is this citation real", but "does it point at the document this
    question is actually supposed to be answered from". An answer with zero citations is not
    grounded by this definition, even if the text itself happens to be factually correct -
    citations_missing is the separate signal for that "correct but uncited" case (see
    domain/answer.py).
    """
    if not answer.citations:
        return False
    return any(citation.document_name in expected_sources for citation in answer.citations)


def abstention_correct(row: EvalRow, answer: Answer) -> bool:
    """For unanswerable rows only: did the system correctly avoid confidently asserting an
    ungrounded answer?

    Correct if EITHER abstained (the model used the documented abstention phrase - the
    explicit signal) OR citations_missing (the model produced no valid, grounded citation for
    its answer - domain/answer.py's independent signal). Reasoning: for a genuinely
    unanswerable question, there is no real source to cite - so a "successful" outcome is any
    answer that does NOT come with a real citation implying it's backed by seed-doc content
    that doesn't actually address the question. A model that stays silent about sourcing
    (citations_missing) is treated the same as one that explicitly declines (abstained): both
    avoid the actual failure mode this metric cares about, which is confidently citing a real
    document as support for an answer to a question that document doesn't actually answer.
    Only case that would fail this check: the model produced a citation to a real seed-doc
    chunk for a question that document doesn't genuinely answer (a real, worse hallucination
    that groundedness alone wouldn't catch here since there's no "expected source" to compare
    against for unanswerable rows).

    Only meaningful for category == "unanswerable" - callers should skip this check entirely
    for answerable rows rather than pass 0.5/interpret a meaningless result.
    """
    return answer.abstained or answer.citations_missing
