"""CitationExtractor Protocol.

Per docs/CODING-GUIDELINES.md section 3/4: the Protocol lives in its own file, apart from
concrete implementations, and every implementation must explicitly subclass it.

Kept as a Protocol rather than a bare function because there's a real future alternative worth
designing for now: today it's regex-matching text markers out of the model's free-form answer;
a future version could instead ask the model for structured/JSON citations directly.
"""

from __future__ import annotations

from typing import Protocol

from knowledge_assistant.domain import Answer, RetrievedChunk


class CitationExtractor(Protocol):
    def extract(self, answer_text: str, chunks: list[RetrievedChunk]) -> Answer: ...
