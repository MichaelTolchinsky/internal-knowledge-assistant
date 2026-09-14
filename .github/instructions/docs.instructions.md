---
applyTo: "**/*.md"
---

# Documentation & Markdown Instructions

Follow [`AGENTS.md`](../../AGENTS.md) for repository change guidelines and operating process.

## Documentation Structure & Separation

1. **Current-State vs Historical Narrative**:
   - `docs/ARCHITECTURE.md` and `README.md` describe the current-state design, components, and workflows.
   - Investigation logs, bug repros, and historical evolution belong in `docs/ENGINEERING-LOG.md`.
   - Never embed chronological step markers ("Step 10", "Step 12 fix-pass") into active architectural descriptions.

2. **Source Code Cleanliness**:
   - Do not cite markdown document paths (such as `docs/ARCHITECTURE.md` or `docs/CODING-GUIDELINES.md`) inside Python docstrings, comments, or error messages.
   - Keep code comments focused on immediate local intent, algorithms, or technical tradeoffs.

3. **Link Maintenance**:
   - Use relative links for repository documents (e.g., `[`AGENTS.md`](../../AGENTS.md)`).
   - Ensure target paths exist on disk.
   - Pointers to external tools must use verified HTTPS URLs.

4. **Tone and Style**:
   - Keep documentation concise, accurate, and contributor-oriented.
   - Use standard ASCII characters across markdown files unless specific domain symbols are required.
