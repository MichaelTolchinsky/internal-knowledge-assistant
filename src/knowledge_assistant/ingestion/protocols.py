"""Protocols for the ingestion package (parsing + chunking).

Per docs/CODING-GUIDELINES.md section 3: Protocols live apart from their concrete
implementations. ingestion/ covers two boundaries (parsing, chunking) per the section 1 layout
comment "ingestion/ # parsing, chunking" - both Protocols share this one file rather than
fragmenting into two near-empty files, matching the spirit of the embeddings/retrieval/prompts/
llm one-protocol-per-package pattern without over-splitting a single package into extra modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from knowledge_assistant.domain import ParsedDocument


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...


class Chunker(Protocol):
    def chunk(self, text: str) -> list[str]: ...
