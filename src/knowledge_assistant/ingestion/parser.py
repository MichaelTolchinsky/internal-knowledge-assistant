"""Concrete document parsers: raw source file -> ParsedDocument (normalized plain text +
content hash). See ingestion/protocols.py for the DocumentParser Protocol these implement.

Dispatch is by file extension - a small dict lookup, not a plugin registry (no framework needed
for three formats).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

from knowledge_assistant.domain import ParsedDocument
from knowledge_assistant.ingestion.protocols import DocumentParser

_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_TRAILING_WHITESPACE_RE = re.compile(r"[ \t]+\n")

# shortcut: a fixed cap, not a configurable/streaming resource-management system. Upgrade path:
# make this a settings.* value if a real ingestion source needs larger PDFs.
_PDF_MAX_PAGES = 500


class ParserError(Exception):
    """Raised when a source file cannot be parsed - a small boundary-specific exception instead
    of letting raw decode/SDK errors leak out."""


def _normalize_whitespace(text: str) -> str:
    """Collapse trailing-line whitespace and excess blank lines; keep paragraph breaks."""
    text = _TRAILING_WHITESPACE_RE.sub("\n", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _content_hash(raw_bytes: bytes) -> str:
    """sha256 of the raw file bytes - matches Document.content_hash's dedupe purpose."""
    return hashlib.sha256(raw_bytes).hexdigest()


def _decode_utf8(raw_bytes: bytes, path: Path) -> str:
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParserError(f"{path}: not valid UTF-8 text") from exc


class MarkdownParser(DocumentParser):
    """Reads .md source, strips a leading YAML frontmatter block if present, and normalizes
    whitespace. Not a full markdown-to-text renderer - markdown syntax is left in place."""

    def parse(self, path: Path) -> ParsedDocument:
        raw_bytes = path.read_bytes()
        text = _decode_utf8(raw_bytes, path)
        text = _FRONTMATTER_RE.sub("", text, count=1)
        return ParsedDocument(
            text=_normalize_whitespace(text), content_hash=_content_hash(raw_bytes)
        )


class TextParser(DocumentParser):
    """Reads .txt source as-is, normalizing whitespace only."""

    def parse(self, path: Path) -> ParsedDocument:
        raw_bytes = path.read_bytes()
        text = _decode_utf8(raw_bytes, path)
        return ParsedDocument(
            text=_normalize_whitespace(text), content_hash=_content_hash(raw_bytes)
        )


class PdfParser(DocumentParser):
    """Extracts text per page via pypdf and joins pages with a paragraph break."""

    def parse(self, path: Path) -> ParsedDocument:
        raw_bytes = path.read_bytes()
        reader = PdfReader(path)
        if len(reader.pages) > _PDF_MAX_PAGES:
            raise ParserError(
                f"{path}: has {len(reader.pages)} pages, exceeds the {_PDF_MAX_PAGES}-page limit"
            )
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages_text)
        return ParsedDocument(
            text=_normalize_whitespace(text), content_hash=_content_hash(raw_bytes)
        )


_PARSERS_BY_SUFFIX: dict[str, DocumentParser] = {
    ".md": MarkdownParser(),
    ".markdown": MarkdownParser(),
    ".txt": TextParser(),
    ".pdf": PdfParser(),
}


def get_parser(path: Path) -> DocumentParser:
    """Picks the parser for `path` by file extension."""
    try:
        return _PARSERS_BY_SUFFIX[path.suffix.lower()]
    except KeyError:
        raise ValueError(f"No parser registered for file extension: {path.suffix!r}") from None
