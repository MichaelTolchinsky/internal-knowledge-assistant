# Internal Knowledge Assistant

A small, production-oriented **RAG (Retrieval-Augmented Generation)** system built to learn
AI engineering concepts end-to-end, not just to ship a demo.

## Scope

Simulates an internal knowledge assistant for a mid-sized SaaS company. Employees ask
natural-language questions; the system retrieves relevant internal documentation (product docs,
runbooks, troubleshooting guides, policies, API docs, onboarding, FAQs) and generates an answer
**grounded only in retrieved context**, with citations back to source documents/chunks.

**Critical requirement:** the assistant must not fall back on the model's general knowledge for
company-specific questions. If retrieved documentation is insufficient, it must say so rather
than hallucinate.

Scoped as a small, incremental build: get the core ingest -> retrieve -> answer -> cite loop
working locally first, then evaluate it, then treat AWS deployment as an optional later phase.

## Goals

Learn and demonstrate, hands-on:

- Document ingestion, chunking, and embeddings (local HuggingFace / Sentence Transformers)
- Vector storage and similarity search with PostgreSQL + pgvector
- Retrieval, context construction, and grounded LLM generation (AWS Bedrock)
- Citations / source attribution
- RAG evaluation (correctness, retrieval quality, groundedness, abstention accuracy, latency, cost)
- Basic observability (structured logging, LangSmith traces)
- Docker Compose for local dev; AWS CDK for optional deployment

Full detail lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Coding conventions live in
[`docs/CODING-GUIDELINES.md`](docs/CODING-GUIDELINES.md). Agent/contributor roles and process
live in [`AGENTS.md`](AGENTS.md).

## Non-Goals

Explicitly out of scope unless requested later: multi-agent systems, LangGraph, MCP, complex
agent orchestration, fine-tuning/model training, Kubernetes, auth/multi-tenancy, a frontend,
a dedicated vector database (Pinecone/Qdrant/Weaviate), hybrid search (until proven necessary),
multiple LLM providers.

## Success Target (initial evaluation milestone)

Evaluation dataset of 20-30 questions:

- >= 80% answer correctness
- >= 90% source retrieval hit rate @5
- >= 90% correct abstention on unanswerable questions
- 0 critical hallucinations on known-answer questions

These are learning targets, not production SLAs - the point is that results are measurable and
reproducible, so future changes (chunking, top-K, embedding model, prompt) can be compared
against a baseline.

## Definition of Done

- Documents can be ingested, chunked, embedded, and stored in pgvector.
- Questions can be submitted through the API; relevant chunks are retrieved.
- The LLM generates grounded answers with citations, and abstains when documentation is insufficient.
- Unit tests cover core deterministic logic; integration tests cover the retrieval path.
- A versioned evaluation dataset exists and metrics are reproducible; a baseline is recorded and
  at least one RAG improvement experiment has been run against it.
- Token/cost and latency are measurable.
- The app runs locally via Docker Compose, with a repeatable seed process.
- AWS deployment is optional and can be added afterward.

## Local Development

Requires Python 3.14+ and Docker.

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" 2>/dev/null || { pip install -e .; pip install pytest pytest-asyncio pytest-timeout httpx ruff pre-commit alembic; }

cd docker && docker compose up -d postgres && cd ..
alembic upgrade head

pytest tests/
```

Run the full stack (app + postgres) with `docker compose up` from `docker/`.

## Status

Skeleton, local Postgres/pgvector setup, and the initial Document/DocumentChunk data model are
in place (Steps 1-3 of the development progression in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#10-development-progression)). No RAG logic
(chunking, embeddings, retrieval, prompts, LLM, API) yet - see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the system design and
[`AGENTS.md`](AGENTS.md) for how work is planned and executed.
