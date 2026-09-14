"""Answer: the final RAG output - text, its citations, and citation/abstention signals.

`abstained` and `citations_missing` are separate, independent signals - not one collapsed
boolean - because they answer different questions and are not mutually exclusive:
- `abstained`: did the answer text match the documented abstention phrase family? This is the
  model explicitly saying it doesn't have enough information - the actual, explicit signal,
  not an inferred one.
- `citations_missing`: did the answer have zero valid citations AND not match the abstention
  phrase? This is a genuinely ambiguous case where a model either hallucinated an answer with
  no real source, or gave a correct grounded answer but simply forgot to include citation
  markers - a citation-format-compliance signal, not a correctness judgment. See
  citations/text_extractor.py for the exact detection logic and why a two-field design (over a
  single 3-way status) was chosen: the two conditions are genuinely independent checks (phrase
  match vs. citation presence), not mutually exclusive states, so a fixed enum of 3
  combinations would be less expressive than two plain booleans.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge_assistant.domain.citation import Citation


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    abstained: bool = False
    citations_missing: bool = False
