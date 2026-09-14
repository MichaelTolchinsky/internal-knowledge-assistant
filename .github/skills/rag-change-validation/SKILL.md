---
name: rag-change-validation
description: Validate changes to ingestion, embeddings, retrieval, prompts, citations, LLM, or API surfaces.
disable-model-invocation: true
---

# RAG Change Validation

Validate functional, schema, or algorithmic changes to the RAG pipeline components.

## Inputs

- Modified file paths across `src/knowledge_assistant/` and `tests/`.
- Expected behavioral shift (e.g., prompt tweak, chunking adjustment, API schema update).

## Affected-Scope Selection

Identify affected sub-systems based on modified paths:
- `ingestion/` (chunking, parsing, document hashing): `tests/unit/test_chunker.py`, `tests/unit/test_parser.py`, `tests/integration/test_ingestion_flow.py`, `tests/integration/test_seed.py`
- `embeddings/` (vector inference, dimension checks): `tests/unit/test_embeddings.py`, `tests/integration/test_ingestion_flow.py`
- `retrieval/` (pgvector cosine search, threshold filtering): `tests/unit/test_retrieval.py`, `tests/integration/test_retrieval.py`
- `prompts/` (template structure, document injection safety): `tests/unit/test_prompts.py`
- `citations/` (marker regex parsing, abstention detection): `tests/unit/test_citations.py`
- `llm/` (inference client, factory dispatch): `tests/unit/test_llm.py`
- `api/` or `rag_service.py` (FastAPI endpoints, composition): `tests/unit/test_api.py`, `tests/integration/test_query_api.py`, `tests/unit/test_observability.py`, `tests/unit/test_rag_service.py`

## Steps

1. **Static Quality Checks**:
   Run code and formatting linters across repository sources:
   ```bash
   ruff check src tests migrations seed
   ruff format --check src tests migrations seed
   ```

2. **Scoped Tests**:
   Execute targeted unit and integration tests based on the affected scope identified above.

3. **Verify Trust & Non-Fallback Boundaries**:
   - Confirm missing configurations raise explicit startup validation errors.
   - Confirm embedding dimension mismatches abort immediately with typed exceptions.
   - Confirm ungrounded queries trigger clean abstention markers (`abstained: true` or `citations_missing: true`), rather than ungrounded hallucination.

## Outputs

Provide a final validation report detailing:
- **Affected Scope**: List of modified modules and corresponding sub-systems.
- **Commands Run**: Exact command lines executed for linting, formatting, and testing.
- **Pass/Fail Results**: Outcome of each check with test counts.
- **Unresolved Risks**: Any residual edge cases, environmental dependencies, or performance implications.

## Completion Criteria

- All targeted unit and integration tests pass cleanly.
- `ruff check` and `ruff format --check` pass without errors or warnings.
- No silent fallbacks, unvalidated defaults, or swallowed exceptions exist in the modified paths.

## Stop and Failure Conditions

- **Linter/Format Failure**: If formatting or lint rules fail, resolve them before proceeding.
- **Test Failure**: If a test fails, diagnose root cause; do not mask failures with broad catches or dummy assertions.
- **Model Output Non-Determinism**: If a test failure stems from random weights in lightweight test models, verify whether it requires a trained model and should be marked `@pytest.mark.requires_real_llm`.
- **Database Schema Mismatch**: If database schema adjustments are required, do not alter existing migrations; add a new migration via Alembic.
