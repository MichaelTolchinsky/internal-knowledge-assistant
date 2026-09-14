---
applyTo: "src/**/*.py,tests/**/*.py,seed/**/*.py,migrations/**/*.py"
---

# Python Coding & Verification Instructions

Follow [`docs/CODING-GUIDELINES.md`](../../docs/CODING-GUIDELINES.md) for full design rules.
Follow [`AGENTS.md`](../../AGENTS.md) for the core operating contract and change loop.

## Architecture & Boundary Rules

1. **Protocol Boundaries**:
   - Keep Protocol definitions in dedicated `protocols.py` files.
   - Concrete implementations must explicitly subclass their target `Protocol` (e.g., `class HuggingFaceEmbeddingModel(EmbeddingModel):`).
   - Do not import concrete implementations into domain logic or RAG orchestration. Wire dependencies in composition points (`dependencies.py`).

2. **Async Operations**:
   - Keep I/O-bound operations (database access, API clients) async.
   - For CPU-bound model inference, run in worker threads using `asyncio.to_thread` while maintaining an async Protocol interface.

3. **Domain Types & Storage**:
   - Domain models in `knowledge_assistant.domain` are pure Python dataclasses without framework dependencies (FastAPI, SQLAlchemy).
   - SQLAlchemy persistence models in `knowledge_assistant.storage.models` map to database tables and are separate from domain types.

4. **Configuration & Settings**:
   - All tunables live in `knowledge_assistant.config.Settings`.
   - Never hardcode defaults in source code; `.env.example` documents required environment variables.
   - Missing configuration must fail fast on startup via Pydantic validation errors.

5. **Clean Docstrings & Comments**:
   - Never cite internal documentation paths (e.g., `docs/ARCHITECTURE.md`, `docs/CODING-GUIDELINES.md`) or historical step numbers (e.g., "Step 5", "Step 9 review") in code comments or docstrings.
   - State engineering rationale and behavior directly.

## Targeted Validation

Run targeted checks on modified modules before running the full test suite:

```bash
# Targeted file lint and format check
ruff check <path-to-file>
ruff format --check <path-to-file>

# Scoped test runs
pytest tests/unit/test_<module>.py
pytest tests/integration/test_<module>.py
```
