"""ParsedDocument: the output of parsing a raw source file, before chunking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    text: str
    content_hash: str
