"""LLMClient Protocol.

Per docs/CODING-GUIDELINES.md section 3/4: the Protocol lives in its own file, apart from
concrete implementations, and every implementation must explicitly subclass it.
"""

from __future__ import annotations

from typing import Protocol

from knowledge_assistant.domain import LLMResponse


class LLMClient(Protocol):
    async def generate(self, prompt: str, *, max_tokens: int) -> LLMResponse: ...
