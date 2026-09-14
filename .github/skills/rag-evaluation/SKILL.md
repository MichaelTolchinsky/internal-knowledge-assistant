---
name: rag-evaluation
description: Run a reproducible baseline-versus-one-variable experiment against a named dataset version.
disable-model-invocation: true
---

# RAG Evaluation

Execute a reproducible evaluation experiment comparing a baseline run against a single-variable modification on a named dataset version.

## Inputs

- `dataset_version`: Named dataset version under `evaluation/dataset/` (e.g., `v1`).
- Target experiment variable: Exactly one configuration variable to change (e.g., `TOP_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, or `PROMPT_TEMPLATE_VERSION`).

## Resource Demands & Environment Safety

- **PostgreSQL Stack**: Requires a running Postgres instance with pgvector (`cd docker && docker compose up -d postgres && cd ..`).
- **Database Migrations & Seed**: Database must be upgraded and seeded (`alembic upgrade head && python seed/seed.py`).
- **Model Downloads**: Requires downloading/loading full local models (`Qwen2.5-0.5B-Instruct` ~1GB and `all-MiniLM-L6-v2` ~90MB).
- **Secrets Protection**:
  - Never read, grep, cat, print, or log `.env` contents.
  - Inspect `.env.example` as the single documented source for configuration variable names and meanings.
  - Secret values, credentials, and database connection strings must never be recorded or exposed in evaluation artifacts.

## Steps

1. **Safe Configuration & Environment Validation**:
   Validate application settings safely via Python startup without printing raw environment strings or secrets:
   ```bash
   python -c "from knowledge_assistant.config import settings; print('Config loaded successfully. Dataset version ready.')"
   ```

2. **Baseline Evaluation Run**:
   Execute the evaluation runner for the baseline state against the named dataset:
   ```bash
   python -m knowledge_assistant.evaluation.runner
   ```
   Save the generated report path printed by the runner (under `evaluation/reports/`).

3. **Apply Single Variable Change**:
   Modify exactly one experiment variable in the execution environment or configuration. Do not change multiple variables simultaneously.

4. **Experiment Evaluation Run**:
   Execute the evaluation runner for the modified configuration:
   ```bash
   python -m knowledge_assistant.evaluation.runner
   ```
   Save the second generated report path.

5. **Compare Runs**:
   Compare the baseline and experiment evaluation reports. Since the evaluation runner does not invent dynamic CLI metadata, record the specific configuration variables and metric differentials directly in the summary output.

## Outputs

Provide a final experiment comparison report containing:
- **Experiment Scope**: Dataset version and the single independent variable modified.
- **Configuration Delta**: Non-secret configuration settings for Baseline vs Experiment (e.g., `TOP_K: 5` -> `TOP_K: 3`).
- **Metric Comparison Table**:
  - Answer Correctness (%)
  - Recall@K (%)
  - Groundedness (%)
  - Abstention Accuracy (%)
  - Retrieval Latency (ms) and Total Latency (ms)
- **Artifact Links**: Relative file paths to the generated markdown reports in `evaluation/reports/`.
- **Observed Trade-offs**: Brief analysis of how the single variable change impacted accuracy vs latency.

## Completion Criteria

- Both baseline and experiment evaluation runs complete without runtime exceptions.
- The single modified variable is clearly identified and documented.
- Non-secret configuration values and all core evaluation metrics are captured and compared.
- No secret values, credentials, or `.env` contents are exposed or printed in the output.

## Stop and Failure Conditions

- **Setup & Database Failure**: If database connection, migration, or seeding fails, abort immediately. Never evaluate against unmigrated or empty databases.
- **Configuration Validation Failure**: If startup fails with a Pydantic `ValidationError`, abort and resolve the invalid configuration.
- **Model Initialization Failure**: If model download or initialization runs out of memory or fails, stop and escalate.
- **Scoring or Dataset Failure**: If dataset records cannot be parsed or evaluation metrics fail during scoring, abort immediately.
