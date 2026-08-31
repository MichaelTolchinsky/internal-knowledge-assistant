"""ParsedDocument: the output of parsing a raw source file, before chunking.

Framework-free per docs/CODING-GUIDELINES.md section 5.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    text: str
    content_hash: str
