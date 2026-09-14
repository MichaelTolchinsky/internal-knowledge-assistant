"""Pydantic request/response models for the API - the HTTP-facing shape, distinct from the
framework-free domain types (knowledge_assistant.domain) per docs/CODING-GUIDELINES.md section 5.
Domain dataclasses are never returned directly from a route - they're mapped to these models.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, field_validator


class QueryRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be empty or whitespace-only")
        return stripped


class CitationResponse(BaseModel):
    """One source attribution - enough to trace the answer back to a specific document/chunk
    (FR3): document_id + document_name identify the source document, chunk_index locates the
    specific chunk within it, snippet is the actual retrieved text (not LLM-generated)."""

    document_id: UUID
    document_name: str
    chunk_index: int
    snippet: str


class QueryResponse(BaseModel):
    """FR2: answer text plus its sources. abstained/citations_missing are surfaced as separate
    fields (not collapsed into one), matching domain.Answer's two-signal design - see
    domain/answer.py for why."""

    answer: str
    citations: list[CitationResponse]
    abstained: bool
    citations_missing: bool
