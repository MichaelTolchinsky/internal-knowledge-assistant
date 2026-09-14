# Internal Knowledge Assistant

A local-first **RAG (Retrieval-Augmented Generation)** learning project built to understand AI engineering concepts end-to-end, without relying on hosted LLM APIs or black-box frameworks. The system simulates an internal knowledge assistant for a mid-sized SaaS company: users submit natural-language questions over internal company documentation, and the assistant retrieves relevant passages from a local vector store to generate answers grounded in retrieved context.

This project focuses on hands-on exploration of ingestion, embeddings, pgvector retrieval, prompt construction, local model inference, citations, and explicit abstention. To keep the learning loop accessible and reproducible on commodity hardware, AWS deployment, AWS Bedrock, and hosted model APIs are explicitly out of scope.

## What This Project Demonstrates

- **RAG Pipeline from First Principles:** Ingestion, recursive character chunking, dense vector retrieval, prompt safety wrapping, and answer generation composed via typed `typing.Protocol` interfaces.
- **Local Hugging Face Models:** Zero-cost embeddings and causal generation running directly on CPU without cloud credentials.
- **Vector Search with pgvector:** PostgreSQL 17 with `pgvector` HNSW indexing for relational and vector persistence.
- **Safety & Grounding Controls:** Delimited prompt context wrapping to mitigate prompt injection, coupled with dual-signal tracking for explicit abstention and citation-format compliance.
- **Measurable Evaluation:** Automated benchmarking across answer correctness, Recall@5, groundedness, abstention accuracy, and latency using a versioned question dataset.

## Local Stack

| Component | Technology | Role |
|---|---|---|
| **API Framework** | FastAPI + Pydantic v2 | Typed HTTP endpoints and request/response models |
| **Vector Database** | PostgreSQL 17 + `pgvector` | Vector storage with HNSW cosine similarity search |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | 384-dimensional dense embeddings on CPU |
| **Language Model** | `Qwen/Qwen2.5-0.5B-Instruct` | Local open-weight instruction-following LLM via `transformers` |
| **Data Persistence** | SQLAlchemy 2.x (Async) + Alembic | Asynchronous relational schema management and migrations |
| **Testing & Quality**| Pytest + Ruff | Unit/integration testing and fast linting/formatting |

*Public Hugging Face models download automatically on first use, cache locally under `~/.cache/huggingface/`, and require no API keys or accounts.*

## Quick Start

### Prerequisites

- Python 3.14+
- Docker and Docker Compose
- `curl`

### Commands

```bash
# 1. Environment and dependencies
cp .env.example .env
python3.14 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pytest pytest-asyncio pytest-timeout httpx ruff pre-commit alembic fpdf2
pre-commit install --config .github/.pre-commit-config.yaml --install-hooks -t pre-commit -t commit-msg

# 2. Database and migrations
cd docker && docker compose up -d postgres && cd ..
alembic upgrade head

# 3. Seed reference documents
python seed/seed.py

# 4. Start API server
uvicorn knowledge_assistant.api.main:app --host 0.0.0.0 --port 8000
```

## Query Example

Submit a query:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the default API rate limit?"}'
```

Representative response:

```json
{
  "answer": "The default API rate limit for a single API key is 100 requests per minute. For enterprise plans, the rate limit can be increased to 500 requests per minute.",
  "citations": [],
  "abstained": false,
  "citations_missing": true
}
```

- `answer`: Generated text from the local LLM.
- `citations`: Structured list of attributed source documents and chunk indices.
- `abstained`: `true` when the model recognizes missing context and states the instructed abstention phrase.
- `citations_missing`: `true` when the model produces an un-cited answer without abstaining. Because `Qwen2.5-0.5B-Instruct` is a compact 0.5B model, it often synthesizes factually correct answers from context while omitting exact citation tags; surfacing this field distinguishes format non-compliance from hallucinations.

## Evaluation Snapshot

Evaluated against [`evaluation/dataset/v1.jsonl`](evaluation/dataset/v1.jsonl) (57 questions, 11 seed documents in [`evaluation/dataset/README.md`](evaluation/dataset/README.md)):

| Metric | Baseline Result | Learning Target | Status |
|---|---|---|---|
| **Answer Correctness** | **79.5%** | >= 80% | Essentially met |
| **Recall@5** (Retrieval Hit Rate) | **100.0%** | >= 90% | Met |
| **Abstention Accuracy** | **92.3%** | >= 90% | Met |
| **Groundedness** (Citation Accuracy) | **0.0%** | Diagnostic only | Known limitation |

The 0.0% groundedness score reflects the 0.5B model's difficulty with strict tag-formatting instructions rather than retrieval failures (Recall@5 is 100%). Running single-variable experiments (e.g., prompt phrasing, chunk size, chunk overlap, top-K, or similarity threshold) against this baseline provides an empirical learning loop:

```bash
python -m knowledge_assistant.evaluation.runner
```

## Scope and Status

The local RAG system is fully implemented and operational locally.

**Out of Scope:**
- Cloud deployment and infrastructure (AWS CDK, Terraform, Kubernetes).
- Hosted LLM APIs (AWS Bedrock, OpenAI, Anthropic).
- Frontend web applications or administrative user interfaces.
- Authentication, authorization, and multi-tenancy.
- Multi-agent frameworks (LangGraph, AutoGen) and dedicated vector SaaS (Pinecone, Qdrant).

## Documentation Links

- **System Design & Flow:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Coding Standards & Protocols:** [`docs/CODING-GUIDELINES.md`](docs/CODING-GUIDELINES.md)
- **Bug Postmortems & History:** [`docs/ENGINEERING-LOG.md`](docs/ENGINEERING-LOG.md)
- **Contributor & Agent Workflow:** [`AGENTS.md`](AGENTS.md)
- **Evaluation Dataset Specification:** [`evaluation/dataset/README.md`](evaluation/dataset/README.md)

## License

This project is licensed under the [MIT License](LICENSE).
