"""Version-agnostic context rendering: wraps retrieved chunks as labeled, escaped `<document>`
data blocks.

Retrieved text is treated as data, not instructions: retrieved chunk content is untrusted. It's
wrapped in labeled `<document>` tags, HTML-escaped via the stdlib `html.escape` so a chunk can't
break out of its tag with literal `<`/`>`/`"` characters. This is a structural mitigation, not a
guarantee the model can't be manipulated by cleverly worded retrieved text - it makes injection
harder to construct and easier to reason about, nothing more.

Shared across prompt template versions (v1, future v2, ...) so this security-load-bearing logic
is written and verified once, not copy-pasted and potentially weakened per version.
"""

from __future__ import annotations

from html import escape

from knowledge_assistant.domain import RetrievedChunk

_NO_CONTEXT_BLOCK = (
    "<no_context>No documents were retrieved for this question - there is no context to "
    "answer from.</no_context>"
)


def render_context(chunks: list[RetrievedChunk]) -> str:
    """Renders retrieved chunks as escaped, labeled `<document>` blocks, or a `<no_context>`
    marker if none were retrieved."""
    if not chunks:
        return _NO_CONTEXT_BLOCK
    return "\n\n".join(_render_chunk(chunk) for chunk in chunks)


def _render_chunk(chunk: RetrievedChunk) -> str:
    name = escape(chunk.document_name, quote=True)
    content = escape(chunk.content, quote=True)
    return f'<document name="{name}" chunk="{chunk.chunk_index}">\n{content}\n</document>'
