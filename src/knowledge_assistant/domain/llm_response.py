"""LLMResponse: the result of one LLM generation call.

Framework-free per docs/CODING-GUIDELINES.md section 5.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMResponse:
    answer: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model_id: str
