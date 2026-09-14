# CODING-GUIDELINES.md

Concrete engineering conventions for this repo. Scope: keep it simple, favor clear separation of
concerns and typed abstractions at every external boundary, and don't import enterprise-scale
machinery this project doesn't need. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for system design
and [`../AGENTS.md`](../AGENTS.md) for process/roles.

## 1. Project Layout

Single small service, no monorepo tooling:

```
src/
  knowledge_assistant/
    api/            # FastAPI routers + Pydantic request/response models
    domain/         # core types: Document, DocumentChunk, RetrievedChunk, Answer, Citation
    ingestion/       # protocols.py (DocumentParser, Chunker) + parser.py, chunker.py, service.py
    embeddings/      # EmbeddingModel protocol + HF implementation
    retrieval/       # Retriever protocol + pgvector implementation
    prompts/         # PromptBuilder protocol + templates, versioning, safety wrapping
    llm/             # LLMClient protocol + Bedrock implementation
    citations/       # CitationExtractor protocol + regex-based text extractor
    storage/         # SQLAlchemy models, repositories (Document/Chunk persistence)
    evaluation/      # eval dataset loader, runner, metrics
    config.py        # settings (env-driven), one place for tunable params
tests/
  unit/
  integration/
  evaluation/
seed/                # seed.py CLI (Step 15) - ingests evaluation/seed_docs/ into Postgres
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

    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

```python
# retrieval/protocol.py
from typing import Protocol
from knowledge_assistant.domain import RetrievedChunk


class Retriever(Protocol):
    def search(self, query_embedding: list[float], top_k: int) -> list[RetrievedChunk]: ...
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
  templates, `BedrockLLMClient`) live next to their protocol, in the same package.
- Concrete implementations must explicitly subclass their `Protocol` (e.g.
  `class HuggingFaceEmbeddingModel(EmbeddingModel):`), not just satisfy it structurally - this
  makes the boundary explicit in the class definition itself, not only via duck typing.
  Subclassing a `typing.Protocol` this way is plain PEP 544 support - no `@runtime_checkable`
  needed, and it doesn't change duck-typing behavior anywhere else.
- Tests get a trivial fake implementing the same `Protocol` (no mocking framework needed for
  these boundaries) - this is what makes unit tests of the RAG service possible without a real
  Postgres or Bedrock call.
- Wire concrete implementations in one composition point (e.g. `config.py` / a small
  `dependencies.py` used by FastAPI's dependency injection), not scattered `import`s of concrete
  classes throughout the codebase.

## 4. External Client Conventions (Bedrock, Postgres/pgvector)

- One class per external boundary, implementing the relevant `Protocol`.
- Async where the underlying call is I/O-bound and a good async client exists (Bedrock via
  `aioboto3`/`boto3` in a thread, Postgres via `asyncpg`/SQLAlchemy async engine). Keep it
  consistent - don't mix sync and async client code within the same layer.
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
(document/chunk id + name + snippet), `Answer` (text + citations + abstained: bool). These live
in `domain/` with no dependency on FastAPI, SQLAlchemy, or any SDK - keeps the core RAG logic
testable in isolation.

## 6. Configuration

All tunables live in one `config.py` (env-driven via Pydantic `BaseSettings`), not hardcoded in
call sites: embedding model name, chunk size/overlap, top-K, similarity threshold, Bedrock model
ID, prompt template path/version. This is what makes the evaluation experiment workflow
(baseline -> change one variable -> re-run) practical.

## 7. Testing

- `pytest` + `pytest-asyncio` (for async client code) + `pytest-timeout` (catch hanging network
  calls in tests).
- Markers: `unit`, `integration`, `evaluation`. Configure `pytest.ini` with `markers =` entries
  and `--strict-markers` so typos fail loudly.
- **Unit tests**: chunking, metadata extraction, prompt construction, retrieval query
  construction, response validation - use fake `Protocol` implementations, no real Postgres or
  Bedrock.
- **Integration tests**: real local Postgres/pgvector via Docker Compose, exercising
  API -> RAG service -> retriever -> DB. Marked `integration`, can be excluded from the fast
  default run.
- **Evaluation tests**: run the versioned eval dataset through the real pipeline and assert
  against the milestone thresholds in `README.md`. Not a substitute for unit tests, and not run
  on every commit if it's slow/costly (Bedrock calls) - run explicitly when evaluating a change.
- One conftest.py per test tier for shared fixtures (test DB session, fake embedding model, fake
  LLM client).

## 8. Lint / Format / Type-Check

- `ruff` for linting and formatting (single tool, fast, no separate `black`/`isort`/`flake8`).
- Type hints throughout; consider `mypy` in basic (non-strict) mode if it stays low-friction -
  skip it entirely if it becomes more overhead than value for a 3-5 day project.
- `pre-commit` hooks: `ruff` (lint + format), a Conventional Commits check, basic hygiene hooks
  (trailing whitespace, end-of-file-fixer). Skip anything requiring a devcontainer or extra
  services.

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
