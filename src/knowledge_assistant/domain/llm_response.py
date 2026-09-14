"""LLMResponse: the result of one LLM generation call."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMResponse:
    answer: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model_id: str
