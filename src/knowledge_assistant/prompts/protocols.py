"""PromptBuilder Protocol.

Per docs/CODING-GUIDELINES.md section 3/4: the Protocol lives in its own file, apart from
concrete implementations, and every implementation must explicitly subclass it.
"""

from __future__ import annotations

from typing import Protocol

from knowledge_assistant.domain import RetrievedChunk


class PromptBuilder(Protocol):
    """Owns template + version + safety wrapping. Retrieved chunk text is untrusted content -
    it is injected as clearly delimited data, never concatenated as instructions."""

    template_version: str

    def build(self, question: str, chunks: list[RetrievedChunk]) -> str: ...
