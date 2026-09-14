# AGENTS.md

Operating contract for human contributors and coding agents working in this repository.
This file defines process, repository layout, commands, verification standards, and boundaries.

System design lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Coding standards live in [`docs/CODING-GUIDELINES.md`](docs/CODING-GUIDELINES.md).

## 1. Repository Map

```
src/
  knowledge_assistant/
    api/            # FastAPI routes, dependencies, and Pydantic schemas
    domain/         # Pure domain dataclasses (Document, RetrievedChunk, Answer, Citation)
    ingestion/      # Document parser, chunker, and shared ingestion service
    embeddings/     # EmbeddingModel Protocol and HuggingFace implementation
    retrieval/      # Retriever Protocol and PostgreSQL/pgvector implementation
    prompts/        # PromptBuilder Protocol, versioned templates, and context rendering
    llm/            # LLMClient Protocol, local HuggingFace client, and factory
    citations/      # CitationExtractor Protocol and regex-based text extractor
    storage/        # SQLAlchemy persistence models, engine, and session management
    evaluation/     # Eval dataset loader, scoring metrics, and evaluation runner
    config.py       # Strict env-driven Settings (no baked defaults, fails fast)
tests/
  unit/             # Fast tests using fake Protocol implementations
  integration/      # End-to-end flows against real PostgreSQL/pgvector
  evaluation/       # Tests for evaluation loader and metrics
seed/               # Standalone seed CLI (seed.py) for local knowledge base population
evaluation/         # Static evaluation dataset (dataset/) and seed corpus (seed_docs/)
migrations/         # Alembic database migrations
docker/             # Dockerfile and docker-compose.yml for local stack
.github/            # GitHub Actions CI, instructions, PR template, and skills (rag-change-validation, rag-evaluation, public-release-audit)
```

## 2. Local Commands

Run commands from the repository root unless specified.

```bash
# Setup environment
cp .env.example .env
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" || { pip install -e .; pip install pytest pytest-asyncio pytest-timeout httpx ruff pre-commit alembic; }
pre-commit install --config .github/.pre-commit-config.yaml --install-hooks -t pre-commit -t commit-msg

# Database management (requires Docker)
cd docker && docker compose up -d postgres && cd ..
alembic upgrade head

# Code formatting and linting
ruff check src tests migrations seed
ruff format --check src tests migrations seed

# Auto-fix formatting and linting
ruff check --fix src tests migrations seed
ruff format src tests migrations seed

# Running tests
pytest tests/                                    # Full test suite (requires local Postgres and real models)
pytest tests/ -q -m "not requires_real_llm"      # CI-compatible test run (avoids large trained LLM requirements)

# Database seeding
python seed/seed.py                              # Ingests evaluation/seed_docs/ into Postgres
python seed/seed.py --source-dir custom_dir/     # Ingests a custom document directory

# Clean teardown
cd docker && docker compose down -v && cd ..
```

## 3. Change Loop

1. **Inspect before modifying**: Check the repository map, target files, and relevant documentation.
2. **Minimal, surgical edits**: Implement the requested change using existing patterns. Do not refactor unrelated code.
3. **Run targeted tests**: Run unit and integration tests scoped to affected areas first.
4. **Run linters and formatters**: Ensure `ruff check` and `ruff format --check` pass without errors.
5. **Run regression tests**: Verify full test suite passes. If a database is required, ensure migrations and seed succeed.
6. **Synchronize documentation**: Update markdown documentation when interfaces, behavior, or configuration changes.

## 4. Acceptance and Completion Criteria

A task is complete only when:
- Code adheres to typed boundaries and `Protocol` subclassing rules in `docs/CODING-GUIDELINES.md`.
- No raw default values are baked into `src/knowledge_assistant/config.py`. All settings come from `.env` with `.env.example` as documentation.
- `ruff check src tests migrations seed` and `ruff format --check src tests migrations seed` pass cleanly.
- `pytest tests/` passes completely on local environments with PostgreSQL running.
- In CI workflows, `pytest tests/ -q -m "not requires_real_llm"` passes against the lightweight test model.
- Documentation reflects actual behavior; internal document paths and step labels are not cited inside Python comments or docstrings.

## 5. Escalation Rules for Ambiguity

Do not guess when hitting ambiguous choices:
- If a configuration requirement conflicts with environment loading or schema validation, stop and escalate.
- If an architectural choice introduces a new external dependency or breaks protocol boundaries, stop and present trade-offs.
- If a test failure stems from a non-deterministic model output versus code logic, isolate and escalate with exact repro steps.
- If destructive operations (database wipes, branch force pushes, file deletions outside ephemeral scratch) are needed, request explicit confirmation.

## 6. Documentation Synchronization

- Documentation must represent current-state architecture and behavior.
- Python docstrings and comments must state technical intent and rationale directly. Never cite document paths (e.g. `docs/ARCHITECTURE.md`, `docs/CODING-GUIDELINES.md`) or historical step numbers (e.g. "Step 5") inside Python source code.
- Keep links between markdown files relative and verified.

## 7. Security and Secrets Handling

- Never commit real credentials, secret keys, or `.env` files containing live secrets.
- `.env.example` contains non-secret placeholders and documentation only.
- In scripts, logs, and error outputs, redact connection strings and passwords. Never log sensitive payloads or query texts in production.
- Sanitize retrieved text chunks before rendering into prompt templates (`html.escape` wrapping in `<document>` blocks) to prevent prompt injection breakouts.

## 8. RAG-Specific Trust Requirements

- **Strict grounding**: Company-specific questions must be answered using retrieved documentation context only.
- **Explicit abstention**: If retrieved chunks lack sufficient information, the system must abstain cleanly (`abstained: true` or `citations_missing: true`), not hallucinate answers from base model weights.
- **Exact citations**: Generated statements must map back to retrieved `(source: <document_name>, chunk <chunk_index>)` markers when the LLM supports it.
- **Fail fast on mismatches**: Embedding dimensions must match vector store column dimensions (`settings.embedding_dimension == 384`). Any mismatch must abort immediately.

## 9. Non-Goals

Do not introduce or accept contributions for:
- Multi-agent orchestration, LangGraph, or AutoGen frameworks.
- Model context protocol (MCP) server integrations within the application runtime.
- Model fine-tuning or custom training pipelines.
- Kubernetes deployment manifests or Helm charts.
- User authentication, multi-tenancy, or permission models.
- Dedicated vector databases (Pinecone, Qdrant, Weaviate, Milvus).
- Web frontends or complex administrative UIs.
- Hybrid keyword-vector search (until empirical evaluation on current datasets demonstrates necessity).
