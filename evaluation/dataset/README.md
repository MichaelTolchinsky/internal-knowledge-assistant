# Evaluation Dataset

## Layout choice

This `evaluation/` directory lives at the repo root, as a **data** sibling to `src/`, `tests/`,
`docker/`, and the future `seed/` directory - not inside `src/knowledge_assistant/evaluation/`.
That `src/knowledge_assistant/evaluation/` package (per `docs/CODING-GUIDELINES.md` section 1)
is reserved for the eval **code** - dataset loader, runner, metrics - which Step 13 adds. Seed
markdown docs and the dataset file are data assets consumed by that code, not code themselves,
so they're kept out of the importable package (mirroring how `seed/` is already anticipated as
a top-level, non-package directory in the project layout).

```
evaluation/
  seed_docs/       # markdown source documents the dataset's questions are written against
  dataset/
    v1.jsonl       # the versioned question set
    README.md      # this file
```

## Seed documents (`seed_docs/`)

11 short but substantive markdown files simulating a mid-sized SaaS company's internal
documentation (per README.md's "Scope": product docs, runbooks, troubleshooting guides,
policies, API docs, onboarding, FAQs):

- `api-rate-limits.md`, `api-versioning-and-deprecation.md` - API docs
- `auth-credential-rotation.md` - security/auth policy
- `deployment-process.md` - engineering runbook
- `log-retention-policy.md`, `data-retention-policy.md` - internal policy
- `production-db-access.md` - internal policy / access control
- `webhook-troubleshooting.md` - troubleshooting guide
- `onboarding-checklist.md` - onboarding doc
- `incident-response.md` - engineering runbook
- `faq.md` - FAQ

Each file has several paragraphs of real, specific content (not one-liners) so a chunker
produces multiple chunks per document, matching how ingestion actually behaves in this project.

## Dataset format (`dataset/v1.jsonl`)

One JSON object per line (JSONL - easy to append to, diff, and stream-read without loading the
whole file, and trivially greppable). Each row:

```json
{
  "id": "q001",
  "question": "What is the default API rate limit?",
  "category": "answerable",
  "expected_answer": "100 requests per minute per API key.",
  "expected_sources": ["api-rate-limits.md"]
}
```

Fields:

- `id` - stable, sequential (`q001`, `q002`, ...) identifier for referencing a specific row in
  eval-run reports/regressions.
- `question` - the natural-language question, as a user would type it.
- `category` - exactly one of `"answerable"` or `"unanswerable"`. `"answerable"` means the seed
  docs genuinely contain the information needed; `"unanswerable"` means they deliberately do
  not, and the correct system behavior is to abstain rather than guess or use general knowledge
  (per README.md's "Critical requirement").
- `expected_answer` - for `"answerable"` rows, the correct factual answer synthesized from the
  seed doc content (what a correct RAG answer should say, in substance - not required to match
  word-for-word, that's a job for the Step 13 runner's scoring logic). For `"unanswerable"`
  rows, this is always the literal sentinel string `"ABSTAIN"` - a fixed, easy-to-check-in-code
  marker meaning "the correct behavior here is abstention," rather than free text describing
  why, so a future eval runner can do a simple equality check instead of parsing prose.
- `expected_sources` - list of seed-doc filenames (matching files in `seed_docs/`) that should
  back the answer. Exactly one filename for every `"answerable"` row in this version - each
  answerable question is deliberately traceable to a single source document (multi-document
  synthesis is out of scope for this dataset version, per the approved task). Always an empty
  list for `"unanswerable"` rows.

## Composition

57 questions: 44 answerable (77.2%), 13 unanswerable (22.8%) - deliberately larger and more
varied than README.md's original 20-30 question success-target baseline, per the approved task.
Answerable questions vary in difficulty: most are single-fact lookups, but several require
combining two related sentences from the same document (e.g. "What HTTP status code is returned
when the rate limit is exceeded, and what header tells you how long to wait?" combines the 429
status and the `Retry-After` header, both from `api-rate-limits.md`). Unanswerable questions
follow README.md's "Unanswerable" categories: future/hypothetical company decisions, personal
contact info, and internal details never documented in the seed docs (e.g. tech stack,
headcount, compensation).

## Versioning

`v1` is a full, closed snapshot: this exact question set is only valid against this exact
`seed_docs/` snapshot - `expected_sources` filenames and `expected_answer` text are written
against the current wording of those files. A `v2` (a new file, e.g. `v2.jsonl`, not an edit to
`v1.jsonl`) is warranted when:

- the seed docs change (content edited, added, or removed) in a way that invalidates existing
  `expected_answer`/`expected_sources` values,
- the dataset needs a materially different composition (more questions, different
  answerable/unanswerable ratio, multi-document synthesis questions), or
- scoring methodology changes enough that old rows no longer make sense (e.g. if
  `expected_answer` needs to become a list of acceptable phrasings instead of one string).

Keep old version files around rather than overwriting them, so past eval runs stay reproducible
against the dataset version they were actually run with (see docs/AGENTS.md's Decision Records
and docs/ARCHITECTURE.md section 3.3's evaluation flow, which explicitly compares runs against a
recorded baseline - that comparison is only meaningful if the baseline's dataset version is
pinned and preserved).

## What this step does NOT do

No evaluation runner exists yet - that's Step 13. `tests/unit/test_evaluation_dataset.py`
validates this dataset file as static data (schema, categories, no duplicate questions,
`expected_sources` filenames actually exist) - it does not run any RAG pipeline or score answer
quality.
