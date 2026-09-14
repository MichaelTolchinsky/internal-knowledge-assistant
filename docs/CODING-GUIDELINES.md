# CODING-GUIDELINES.md

Concrete engineering conventions for this repo. Scope: keep it simple, favor clear separation of
concerns and typed abstractions at every external boundary, and don't import enterprise-scale
machinery this project doesn't need. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for system design
and [`../AGENTS.md`](../AGENTS.md) for the repository process and boundaries.

## 1. Project Layout

Single small service, no monorepo tooling:

```
src/
  knowledge_assistant/
    api/            # FastAPI routers + Pydantic request/response models
    domain/         # core types: Document, DocumentChunk, RetrievedChunk, Answer, Citation
    ingestion/      # protocols.py (DocumentParser, Chunker) + parser.py, chunker.py, service.py
    embeddings/     # EmbeddingModel protocol + HF implementation
    retrieval/       # Retriever protocol + pgvector implementation
    prompts/        # PromptBuilder protocol + templates, versioning, safety wrapping
    llm/            # LLMClient protocol + local HF implementation (Bedrock deferred)
    citations/      # CitationExtractor protocol + regex-based text extractor
    storage/        # SQLAlchemy models, repositories (Document/Chunk persistence)
    evaluation/     # eval dataset loader, runner, metrics
    config.py       # settings (env-driven), one place for tunable params
tests/
  unit/
  integration/
  evaluation/
seed/               # seed.py CLI - ingests evaluation/seed_docs/ into Postgres
docker/
  Dockerfile
  docker-compose.yml
```

Rule: a module should not reach across layers (e.g. `api/` must not construct a Bedrock client
directly - it calls into `domain`/service code that depends on the `LLMClient` protocol).

## 2. Separation of Concerns

Keep these concerns in distinct modules, each with a narrow interface:

- **Ingestion** (parse -> chunk) is independent of **embedding generation**, which is independent
  of **persistence**. Each should be callable/testable in isolation.
- **Retrieval** (vector search) is independent of **prompt construction** (the Prompt Service),
  which is independent of **LLM invocation** (the LLM Client). Prompt templates get their own
  module (`prompts/`) rather than living inside `llm/`, because "which prompt produced this
  answer" needs to be versioned and evaluated independently of "which model/transport was used".
- The RAG "service" layer orchestrates these; it contains no HTTP concerns and no SQL and no
  Bedrock SDK calls itself - it composes the protocols below.

This mirrors the project's own stated learning goal: every stage of the pipeline must be
independently inspectable, not hidden behind one framework call.

## 3. Abstractions via `typing.Protocol`

Every external boundary (embedding backend, vector store, LLM provider) is defined as a
`Protocol`, not an ABC and not a concrete class used directly. This keeps implementations
swappable (a core experimentation goal - trying different embedding models, or the local
Bedrock client vs a fake for tests) without inheritance coupling.

```python
# embeddings/protocol.py
from typing import Protocol


class EmbeddingModel(Protocol):
    """Turns text into a fixed-dimension vector. Query and document text must use the
    same implementation/model so vectors are comparable."""

    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

```python
# retrieval/protocol.py
from typing import Protocol
from knowledge_assistant.domain import RetrievedChunk


class Retriever(Protocol):
    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float | None = None,
    ) -> list[RetrievedChunk]: ...
```

```python
# prompts/protocol.py
from typing import Protocol
from knowledge_assistant.domain import RetrievedChunk


class PromptBuilder(Protocol):
    """Owns template + version + safety wrapping. Retrieved chunk text is untrusted content -
    it is injected as clearly delimited data, never concatenated as instructions."""

    template_version: str

    def build(self, question: str, chunks: list[RetrievedChunk]) -> str: ...
```

```python
# llm/protocol.py
from typing import Protocol
from knowledge_assistant.domain import LLMResponse


class LLMClient(Protocol):
    async def generate(self, prompt: str, *, max_tokens: int) -> LLMResponse: ...
```

Guidelines for these protocols:

- Keep the method surface minimal - only what the RAG service actually calls.
- Concrete implementations (`HuggingFaceEmbeddingModel`, `PgVectorRetriever`, `PromptBuilder`
  templates, `LocalLLMClient`, and future `BedrockLLMClient`) live next to their protocol, in the same package.
- Concrete implementations must explicitly subclass their `Protocol` (e.g.
  `class HuggingFaceEmbeddingModel(EmbeddingModel):`), not just satisfy it structurally - this
  makes the boundary explicit in the class definition itself, not only via duck typing.
  Subclassing a `typing.Protocol` this way is plain PEP 544 support - no `@runtime_checkable`
  needed, and it doesn't change duck-typing behavior anywhere else.
- Tests get a trivial fake implementing the same `Protocol` (no mocking framework needed for
  these boundaries) - this is what makes unit tests of the RAG service possible without a real
  Postgres or model call.
- Wire concrete implementations in one composition point (e.g. `config.py` / a small
  `dependencies.py` used by FastAPI's dependency injection), not scattered `import`s of concrete
  classes throughout the codebase.

## 4. External Client Conventions (Postgres/pgvector, Bedrock)

- One class per external boundary, implementing the relevant `Protocol`.
- Currently implemented: local CPU inference for embeddings (`HuggingFaceEmbeddingModel` offloaded
  via `asyncio.to_thread`) and local LLM generation (`LocalLLMClient` via `asyncio.to_thread`),
  along with async PostgreSQL/pgvector via `asyncpg`/SQLAlchemy async engine (`PgVectorRetriever`).
- Future AWS Bedrock client: implement via async-native `aioboto3` (rather than blocking `boto3` in a thread)
  to avoid thread-pool exhaustion at concurrency scale.
- Explicit timeouts and a small, explicit retry policy (e.g. `tenacity` with bounded retries) on
  network calls. No silent retry-forever loops.
- A small, explicit exception hierarchy per boundary (e.g. `LLMClientError`,
  `RetrievalError`) instead of letting raw SDK exceptions leak into the API layer. The API layer
  translates these into HTTP responses (including the "insufficient context, abstaining" case,
  which is a normal outcome, not an error).
- No raw HTTP/SDK calls inline in route handlers or the RAG service - always through the
  client/protocol.

## 5. Domain Types

Central typed domain objects (dataclasses or Pydantic models, not raw dicts) shared across
layers: `Document`, `DocumentChunk`, `RetrievedChunk` (chunk + similarity score), `Citation`
(document/chunk id + name + snippet), `Answer` (text + citations + abstained: bool +
citations_missing: bool). These live in `domain/` with no dependency on FastAPI, SQLAlchemy, or
any SDK - keeps the core RAG logic testable in isolation.

## 6. Configuration

All tunables live in one `config.py` (env-driven via Pydantic `BaseSettings`), not hardcoded in
call sites: embedding model name, chunk size/overlap, top-K, similarity threshold, local LLM
model name (and future Bedrock model ID/region), prompt template path/version. This is what
makes the evaluation experiment workflow (baseline -> change one variable -> re-run) practical.

## 7. Testing

- `pytest` + `pytest-asyncio` (for async client code) + `pytest-timeout` (catch hanging network
  calls in tests).
- Markers: `unit`, `integration`, `evaluation`, `requires_real_llm`. Configured in `pyproject.toml`
  under `[tool.pytest.ini_options]` with `markers =` entries.
- Test directory layout:
  - `tests/unit/`: fast unit tests covering chunking, metadata extraction, prompt construction,
    retrieval query construction, response validation, domain types, and API routers using fake
    `Protocol` implementations (no real Postgres or heavy model downloads).
  - `tests/integration/`: real local Postgres/pgvector via Docker Compose, exercising
    API -> RAG service -> retriever -> DB, migrations, seeding, and real embedding models.
  - `tests/evaluation/`: dataset loading, metrics scoring, and eval runner mechanics.
- Evaluation runs against the full evaluation dataset are on-demand via `python -m knowledge_assistant.evaluation.runner`
  or targeted pytest runs, rather than on every commit when slow/heavy model inference is involved.
- `conftest.py` provides shared fixtures (test DB session, fake protocols).

## 8. Lint / Format / Type-Check

- `ruff` for linting and formatting (single tool, fast, no separate `black`/`isort`/`flake8`).
- Type hints throughout; consider `mypy` in basic (non-strict) mode if it stays low-friction -
  skip it entirely if it becomes more overhead than value for a 3-5 day project.
- `.github/.pre-commit-config.yaml` defines the `pre-commit` hooks: `ruff` (lint + format), a
  Conventional Commits check, and basic hygiene hooks (trailing whitespace, end-of-file-fixer).
  Skip anything requiring a devcontainer or extra services.

## 9. Commits / PRs

- Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`).
- Small, focused commits per development-progression step (see [`ARCHITECTURE.md`](ARCHITECTURE.md) section 10).
- PR/commit description states: what changed, how it was tested, any new/changed env vars or
  config.

## 10. Docker

- One `Dockerfile` for the app, one `docker-compose.yml` for local dev: `app` + `postgres`
  (pgvector-enabled image) only. No Redis/Temporal/devcontainer/emulator unless a concrete AWS
  integration later needs local emulation - in that case add [Floci](https://floci.io) as an
  extra `docker-compose` service (free, open-source, drop-in-compatible LocalStack alternative),
  not before.
- Postgres pinned to a specific major version; pgvector extension enabled via init SQL/migration,
  not manually per environment.

## 11. What We Are Deliberately Not Doing

No LangGraph/agent-graph state machinery, no MCP server scaffolding, no multi-service test
containers, no Nx-style build graph, no `pyright` unless it proves valuable, no enterprise
citations framework - our citation need is fully met by the `Citation` domain type above. These
were present in a larger reference platform but are explicit non-goals here (see `README.md`
section "Non-Goals").
