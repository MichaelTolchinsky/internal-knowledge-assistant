# ARCHITECTURE.md

Proposed system design for the Internal Knowledge Assistant. This is a **proposal pending
developer approval** per the project's "stop and report" requirement - no application code has
been written yet.

## 1. Technology Choices & Tradeoffs

| Concern | Choice | Alternatives considered | Reason |
|---|---|---|---|
| Vector storage | PostgreSQL + pgvector | Pinecone, Qdrant, Weaviate | One datastore for relational metadata + vectors; avoids operating a second system; sufficient for this scale; explicit non-goal to introduce a dedicated vector DB. |
| Embeddings | Local HuggingFace / Sentence Transformers | Bedrock/OpenAI embedding APIs | Educational: understand embedding inference directly instead of treating it as a black box. Zero marginal cost per embed. Must keep query/document embeddings on the same model. |
| LLM | AWS Bedrock, behind an abstraction | Direct OpenAI/Anthropic SDK | Matches target AWS deployment; abstraction keeps the app from being tightly coupled to Bedrock-specific request/response shapes. Single provider - no concrete learning reason yet to support multiple. |
| API framework | FastAPI + Pydantic | Flask, Django | Async-friendly, typed request/response models, fast to iterate. |
| ORM | SQLAlchemy 2.x | raw SQL, Django ORM | Typed models, migrations story, works naturally with pgvector's SQLAlchemy integration. |
| Retrieval | Vector similarity search only | Hybrid (keyword + vector) | Hybrid adds complexity; only add later if evaluation shows a concrete gap. |
| Local dev | Docker Compose (FastAPI + Postgres/pgvector) | LocalStack for AWS emulation | LocalStack only added if a specific AWS integration needs it - not by default. |
| Observability | Structured logging + LangSmith | Custom observability platform | LangSmith covers LLM/RAG tracing; no need to build our own. |
| IaC | AWS CDK (Python) | Terraform, CloudFormation | Python-native, matches app language, optional/deferred until local system works. |

## 2. High-Level Architecture

```
Client
  |
  v
FastAPI
  |
  v
RAG Service
  |-- Retriever --> PostgreSQL + pgvector
  |
  |-- LLM (abstraction) --> AWS Bedrock

Document Ingestion (separate path)
  |
  v
Document Parser -> Chunker -> Embedding Generator -> PostgreSQL + pgvector
```

Exact module boundaries are decided during implementation, but ingestion and query-time paths
are kept separate: ingestion is a batch/offline concern (seed later), query answering is the
online request path.

## 3. Core System Flows

### 3.1 Ingestion Flow

```
Load document (md / txt / pdf)
  -> Extract text
  -> Create document metadata (name, source, content_hash, metadata)
  -> Split into chunks (configurable size/overlap)
  -> Generate embeddings (local HF model)
  -> Persist document + chunks + embeddings (Postgres/pgvector)
```

Repeatable/idempotent: re-running ingestion on the same content should not duplicate data
(content_hash is the natural dedupe key).

### 3.2 Query Flow (RAG pipeline)

```
User question
  -> Question embedding (same model as documents)
  -> Vector search (pgvector similarity, top-K)
  -> Top-K chunks (+ optional distance/similarity threshold)
  -> Context construction (assemble prompt from chunks + citations metadata)
  -> LLM call (Bedrock, via abstraction)
  -> Answer
  -> Citations (document/chunk IDs mapped back to retrieved context)
  -> If context is insufficient -> explicit abstention, not a guess
```

Every stage must be independently inspectable (no single framework call hiding the whole
pipeline) - this is a stated learning objective, not an implementation nicety.

### 3.3 Evaluation Flow

```
Baseline run over versioned eval dataset (20-30 Q/A pairs)
  -> Record: answer correctness, Recall@K, groundedness, abstention accuracy, latency, cost
  -> Change one variable (chunk size / overlap / top-K / threshold / prompt / embedding model)
  -> Re-run evaluation
  -> Compare against baseline
  -> Keep or discard the change based on evidence
```

## 4. Data Model (conceptual, initial)

```
Document
--------
id
name
source
content_hash
metadata
created_at
updated_at

DocumentChunk
-------------
id
document_id (FK -> Document)
chunk_index
content
embedding        (pgvector column; dimension tied to chosen embedding model)
metadata
created_at
```

Exact column types, indexes (e.g. HNSW/IVFFlat on `embedding`), and constraints to be finalized
during the data-model implementation step.

## 5. Configurable Parameters

To support the experimentation goals in the handoff spec, these are first-class config, not
hardcoded:

- Embedding model
- Chunk size / chunk overlap
- Top-K
- Similarity/distance threshold
- Prompt template

## 6. API Surface (initial)

```
POST /query
  request:  { "question": "..." }
  response: { "answer": "...", "sources": [...] }
```

Exact response schema (source object shape: document name/id, chunk id, relevant text/location)
finalized during API implementation. A separate ingestion endpoint/command is deferred until the
core query flow is validated (per the "no seeding during planning" rule).

## 7. Observability

Per request, track: request ID, question, retrieved chunk IDs, retrieval latency, model used,
token usage, LLM latency, total latency. Structured logs by default; LangSmith traces where they
add value for LLM/RAG-specific debugging. No custom observability platform.

## 8. Security Considerations (documented risks, not enterprise controls)

- Secrets via environment variables only; nothing committed to Git.
- Prompt injection risk from untrusted/retrieved document content - treat retrieved text as data,
  not instructions, in prompt construction.
- Excessive context injection - bound context size, don't dump entire documents.
- Sensitive data exposure - be mindful of what internal docs get ingested and surfaced via
  citations.

## 9. Cost Considerations

Local Postgres + local HF embedding inference during development; Bedrock calls only for
necessary LLM inference; small eval dataset and small seed documents; no always-on AWS
infrastructure until an optional deployment phase is explicitly greenlit.

## 10. Development Progression

```
1. Project skeleton
2. PostgreSQL + pgvector (Docker Compose)
3. Document/chunk data model
4. Chunking
5. Embeddings
6. Vector retrieval
7. LLM generation
8. Citations
9. API
10. Tests (unit + integration)
11. Evaluation dataset
12. Evaluation runner
13. Observability
14. Seed service
15. Optional AWS deployment (CDK)
```

Each step is followed by a Learning Gate (see [`../AGENTS.md`](../AGENTS.md)) before the next one starts.

## 11. Open Decisions (to resolve at the relevant implementation step, not now)

- Specific embedding model + vector dimension.
- Initial chunk size/overlap and the reasoning for it.
- Initial top-K and threshold.
- pgvector index type (HNSW vs IVFFlat) and distance metric (cosine vs L2 vs inner product).
- Prompt template for grounded, citation-aware, abstention-capable answers.
- Evaluation dataset format and scoring method for "answer correctness" and "groundedness".
