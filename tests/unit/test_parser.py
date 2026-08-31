"""Unit tests for document parsers (tests/unit - no DB/network, pure functions on real files)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fpdf import FPDF

from knowledge_assistant.ingestion.parser import (
    MarkdownParser,
    ParserError,
    PdfParser,
    TextParser,
    get_parser,
)


@pytest.mark.unit
def test_markdown_parser_strips_frontmatter_and_normalizes_whitespace(tmp_path: Path) -> None:
    raw = "---\ntitle: API Security\ntags: [security]\n---\n\n# Heading\n\nSome   text.  \n\n\n\nMore text.\n"
    path = tmp_path / "doc.md"
    path.write_bytes(raw.encode("utf-8"))

    parsed = MarkdownParser().parse(path)

    assert "title: API Security" not in parsed.text
    assert parsed.text == "# Heading\n\nSome   text.\n\nMore text."
    assert parsed.content_hash == hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.mark.unit
def test_markdown_parser_without_frontmatter_is_left_intact(tmp_path: Path) -> None:
    raw = "# No frontmatter here\n\nJust content.\n"
    path = tmp_path / "plain.md"
    path.write_bytes(raw.encode("utf-8"))

    parsed = MarkdownParser().parse(path)

    assert parsed.text == "# No frontmatter here\n\nJust content."


@pytest.mark.unit
def test_text_parser_normalizes_whitespace(tmp_path: Path) -> None:
    raw = "Line one.   \nLine two.\n\n\n\nLine three.\n"
    path = tmp_path / "notes.txt"
    path.write_bytes(raw.encode("utf-8"))

    parsed = TextParser().parse(path)

    assert parsed.text == "Line one.\nLine two.\n\nLine three."
    assert parsed.content_hash == hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.mark.unit
def test_pdf_parser_extracts_real_text(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Hello from a real PDF fixture.")
    pdf.output(str(path))

    parsed = PdfParser().parse(path)

    assert "Hello from a real PDF fixture." in parsed.text
    assert parsed.content_hash == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.unit
def test_content_hash_is_stable_across_repeated_parses(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"same bytes every time")

    first = TextParser().parse(path)
    second = TextParser().parse(path)

    assert first.content_hash == second.content_hash


@pytest.mark.unit
def test_get_parser_dispatches_by_extension(tmp_path: Path) -> None:
    assert isinstance(get_parser(tmp_path / "a.md"), MarkdownParser)
    assert isinstance(get_parser(tmp_path / "a.txt"), TextParser)
    assert isinstance(get_parser(tmp_path / "a.pdf"), PdfParser)


@pytest.mark.unit
def test_get_parser_raises_for_unknown_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="docx"):
        get_parser(tmp_path / "a.docx")


@pytest.mark.unit
def test_text_parser_raises_parser_error_for_non_utf8_bytes(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"\xff\xfe not valid utf-8")

    with pytest.raises(ParserError, match=str(path)):
        TextParser().parse(path)


@pytest.mark.unit
def test_markdown_parser_raises_parser_error_for_non_utf8_bytes(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_bytes(b"\xff\xfe not valid utf-8")

    with pytest.raises(ParserError, match=str(path)):
        MarkdownParser().parse(path)


@pytest.mark.unit
def test_pdf_parser_rejects_files_over_the_page_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import knowledge_assistant.ingestion.parser as parser_module

    monkeypatch.setattr(parser_module, "_PDF_MAX_PAGES", 1)

    path = tmp_path / "doc.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Page one.")
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Page two.")
    pdf.output(str(path))

    with pytest.raises(ParserError, match="page"):
        PdfParser().parse(path)
