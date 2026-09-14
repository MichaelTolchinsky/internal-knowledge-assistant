# Internal Knowledge Assistant

A local-first **RAG (Retrieval-Augmented Generation)** learning project built to understand AI engineering concepts end-to-end, without relying on hosted LLM APIs or black-box frameworks.

The system simulates an internal knowledge assistant for a mid-sized SaaS company. Users submit natural-language questions over internal company documentation (rate limits, deployment runbooks, auth policies, database access, FAQs). The assistant retrieves relevant chunked context from a local vector store and generates answers **grounded exclusively in the retrieved documentation**, identifying sources and explicitly abstaining when information is absent.

## Learning Objectives

- Build every layer of a RAG pipeline from first principles using focused third-party libraries and typed `Protocol` boundaries.
- Run local Hugging Face embedding and causal language models on commodity hardware with zero API token costs.
- Store document chunks and perform vector similarity search using PostgreSQL with the `pgvector` extension.
- Isolate untrusted retrieved context using structural delimiters and prompt safety techniques to mitigate prompt injection.
- Parse citations and implement clean abstention detection without confusing format misses with hallucinations.
- Build reproducible RAG evaluation benchmarks measuring answer correctness, recall, groundedness, abstention accuracy, and latency.

> **Scope Note:** This project is intentionally local-first and educational. Cloud deployment, AWS CDK, and AWS Bedrock are out of scope. All runtime components run on local infrastructure.

---

## Architecture & End-to-End Flow

Every pipeline stage is implemented as an independent, inspectable module orchestrated by a lightweight service layer:

```
[ Documents (Markdown / Text / PDF) ]
                  │
                  ▼
   1. Ingestion & Parsing (pypdf, custom text/markdown parsers)
                  │
                  ▼
   2. Recursive Character Chunking (chunk_size: 800, chunk_overlap: 100)
                  │
                  ▼
   3. Local Embedding Inference (sentence-transformers/all-MiniLM-L6-v2)
                  │
                  ▼
   4. Vector Persistence & Indexing (PostgreSQL 17 + pgvector HNSW cosine)
                  │
  ┌───────────────┴──────────────────────────────────────┐
  │ Query Flow                                            │
  ▼                                                       ▼
[ User Question via FastAPI ]                    [ Ingested Corpus ]
  │                                                       │
  ▼                                                       │
Query Embedding (all-MiniLM-L6-v2)                        │
  │                                                       │
  ▼                                                       │
Cosine Similarity Retrieval (Top-K = 5) ◄─────────────────┘
  │
  ▼
Context Rendering & Safety Wrapping (Escaped XML <document> tags)
  │
  ▼
Prompt Construction (v1 grounded instruction template)
  │
  ▼
Local LLM Generation (Qwen/Qwen2.5-0.5B-Instruct via transformers)
  │
  ▼
Citation Extraction & Abstention Parsing (Regex markers & phrase detection)
  │
  ▼
JSON Response (answer, citations, abstained, citations_missing)
```

### Local Models

- **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors). Fast, lightweight, and runs on CPU.
- **Generation Model:** `Qwen/Qwen2.5-0.5B-Instruct` (0.5B parameter instruction-tuned causal language model). Runs locally via Hugging Face `transformers` and `torch`.

Both models download automatically from Hugging Face on initial run and are cached locally in `~/.cache/huggingface/`. No API keys or paid accounts are required.

---

## Key Features

- **Typed Protocol Abstractions:** `EmbeddingModel`, `Retriever`, `PromptBuilder`, `LLMClient`, and `CitationExtractor` are clean `typing.Protocol` interfaces, keeping components swappable and testable with lightweight fakes.
- **Fail-Fast Configuration:** Centralized settings in `config.py` driven by `pydantic-settings`. No fallback defaults are baked into source code; missing variables fail on startup.
- **Prompt Injection Defense:** Retrieved chunks are treated as untrusted data, escaped with `html.escape`, and enclosed in labeled `<document>` tags.
- **Two-Dimensional Grounding Signals:** Differentiates explicit abstention (`abstained: true`) from format compliance issues (`citations_missing: true`), avoiding false-positive accuracy reporting.
- **Evaluation Benchmark:** Automated evaluation harness scoring test sets on correctness, Recall@5, groundedness, and abstention accuracy against versioned datasets.
- **Repeatable Seeding:** Idempotent database population CLI (`seed.py`) indexing reference documents with deterministic content hashing.

---

## Technology Stack

| Layer | Component | Choice & Rationale |
|---|---|---|
| **Vector Database** | PostgreSQL 17 + `pgvector` | Single relational datastore for relational metadata and vector embeddings with HNSW indexing. |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | 384-dimensional local sentence embeddings, zero API cost, CPU-friendly. |
| **Language Model** | `Qwen/Qwen2.5-0.5B-Instruct` | Local open-weight instruction-following LLM for zero-cost generation. |
| **API Framework** | FastAPI + Pydantic v2 | High-performance asynchronous API with typed request/response contracts. |
| **Data Persistence** | SQLAlchemy 2.x (Async) + Alembic | Asynchronous database access and migration tracking. |
| **Observability** | Structured Logging + LangSmith | JSON-structured logging with optional LangSmith tracing for query debugging. |
| **Testing & Quality**| Pytest + Ruff | Unit and integration test suites, strict linting, and automated formatting. |

---

## Quick Start

### Prerequisites

- Python 3.14+
- Docker and Docker Compose
- `curl` or an HTTP client

### 1. Environment Setup

Clone the repository and initialize the virtual environment:

```bash
cp .env.example .env
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pytest pytest-asyncio pytest-timeout httpx ruff pre-commit alembic fpdf2
pre-commit install --config .github/.pre-commit-config.yaml --install-hooks -t pre-commit -t commit-msg
```

*Note: `.env.example` provides default configuration keys. Never store production credentials or private keys in tracked files.*

### 2. Start PostgreSQL & Apply Migrations

Start the PostgreSQL service container with `pgvector`:

```bash
cd docker && docker compose up -d postgres && cd ..
alembic upgrade head
```

### 3. Ingest Knowledge Base

Run the seed CLI to parse, chunk, embed, and index the reference corpus (`evaluation/seed_docs/`):

```bash
python seed/seed.py
```

### 4. Start the Application API

Run the FastAPI application locally:

```bash
uvicorn knowledge_assistant.api.main:app --host 0.0.0.0 --port 8000
```

---

## Query Example

Submit a query via `curl`:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the default API rate limit?"}'
```

### Representative Response

```json
{
  "answer": "The default API rate limit for a single API key is 100 requests per minute. For enterprise plans, the rate limit can be increased to 500 requests per minute.",
  "citations": [],
  "abstained": false,
  "citations_missing": true
}
```

### Response Field Semantics

- `answer`: Generated answer text from the local LLM.
- `citations`: Extracted structured citations referencing source documents and chunk IDs.
- `abstained`: `true` if the model recognized that the retrieved context did not contain enough information and explicitly invoked the instructed abstention phrase.
- `citations_missing`: `true` if the answer was generated without valid citation markers while not abstaining. Because `Qwen2.5-0.5B-Instruct` is a compact 0.5B parameter model, it frequently answers correctly from retrieved context while omitting exact citation markup. Surfacing `citations_missing` ensures this instruction-following limitation is visible rather than conflated with hallucinations or abstentions.

---

## Evaluation Baseline

The repository includes a versioned evaluation dataset in [`evaluation/dataset/v1.jsonl`](evaluation/dataset/v1.jsonl) containing 57 questions (44 answerable, 13 unanswerable) written against 11 internal seed documents.

Baseline performance recorded using `Qwen2.5-0.5B-Instruct` and `all-MiniLM-L6-v2`:

| Metric | Baseline Result | Learning Target | Status |
|---|---|---|---|
| **Answer Correctness** | **79.5%** | >= 80% | Essentially met |
| **Recall@5** (Retrieval Hit Rate) | **100.0%** | >= 90% | Met |
| **Abstention Accuracy** | **92.3%** | >= 90% | Met |
| **Groundedness** (Citation Accuracy) | **0.0%** | Diagnostic only | Known limitation (see below) |

### Understanding the Groundedness Result

Groundedness requires the model to output exact citations naming the expected document. While retrieval recall is 100% and factual correctness is ~80%, the compact 0.5B parameter model often fails to follow the complex formatting instructions required to generate `(source: doc.md, chunk 0)` citation tags.

Running one-variable tuning experiments (testing prompt wording, chunk geometry, top-K, or similarity threshold) against this baseline is an ongoing learning opportunity supported by the evaluation suite:

```bash
python -m knowledge_assistant.evaluation.runner
```

---

## Project Layout

```
.
├── src/knowledge_assistant/
│   ├── api/            # FastAPI routes, schemas, and dependencies
│   ├── domain/         # Core dataclasses (Document, RetrievedChunk, Answer, Citation)
│   ├── ingestion/      # Document parser, chunker, and ingestion service
│   ├── embeddings/     # EmbeddingModel protocol and Hugging Face implementation
│   ├── retrieval/      # Retriever protocol and pgvector implementation
│   ├── prompts/        # PromptBuilder protocol, templates, and safety escaping
│   ├── llm/            # LLMClient protocol and local transformers client
│   ├── citations/      # CitationExtractor protocol and regex parsing logic
│   ├── storage/        # SQLAlchemy persistence models and async engine
│   ├── evaluation/     # Dataset loader, scoring metrics, and evaluation runner
│   └── config.py       # Pydantic Settings loaded from environment
├── tests/
│   ├── unit/           # Fast unit tests using fake protocol implementations
│   ├── integration/    # Database and retrieval integration tests
│   └── evaluation/     # Evaluation runner and dataset integrity tests
├── seed/               # Standalone seed CLI (seed.py)
├── evaluation/         # Static evaluation dataset (v1.jsonl) and seed documents
├── docker/             # Docker Compose configuration for PostgreSQL
├── docs/               # Architecture specs, coding guidelines, and engineering log
└── .github/            # GitHub Actions CI, instructions, and workflow skills
```

---

## Development Commands

Run all commands from the repository root:

```bash
# Code formatting and linting
ruff check src tests migrations seed
ruff format --check src tests migrations seed

# Auto-fix formatting and linting
ruff check --fix src tests migrations seed
ruff format src tests migrations seed

# Run test suite
pytest tests/ -q -m "not requires_real_llm"      # Fast test suite (used in CI)
pytest tests/                                    # Full test suite (requires local Postgres & models)

# Database migrations
alembic upgrade head                             # Apply pending migrations
alembic revision --autogenerate -m "description" # Generate new migration

# Teardown local containers
cd docker && docker compose down -v && cd ..
```

---

## Limitations & Non-Goals

The following areas are explicitly outside the scope of this learning project:

- **Cloud Deployment:** No AWS CDK, Terraform, Kubernetes, or hosted cloud resources.
- **Hosted Model APIs:** No integrations with AWS Bedrock, OpenAI, or Anthropic APIs.
- **Multi-Agent Orchestration:** No LangGraph, AutoGen, or agent-loop frameworks.
- **Specialized Vector SaaS:** No Pinecone, Qdrant, or Weaviate; PostgreSQL with `pgvector` is the sole datastore.
- **User Authentication:** No JWT, OAuth2, or multi-tenant permission layers.
- **Web User Interface:** No React, Vue, or frontend web client; interactions occur via HTTP API.

---

## Status

The local RAG learning system is implemented and working end-to-end. Ingestion, pgvector similarity search, prompt construction, local Hugging Face model inference, citation/abstention evaluation, and the FastAPI service are fully operational locally. Cloud deployment to AWS and Bedrock integration are intentionally excluded.

---

## Documentation

- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**: System design, domain models, and technical trade-offs.
- **[`docs/CODING-GUIDELINES.md`](docs/CODING-GUIDELINES.md)**: Coding conventions, `typing.Protocol` boundaries, and testing patterns.
- **[`docs/ENGINEERING-LOG.md`](docs/ENGINEERING-LOG.md)**: Postmortems of real bugs, edge cases, and design iterations encountered during development.
- **[`AGENTS.md`](AGENTS.md)**: Operating contract, change loop, acceptance criteria, and repository boundaries for human and agent workflows.

---

## License

This project is licensed under the [MIT License](LICENSE).
