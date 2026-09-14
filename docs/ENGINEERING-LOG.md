# ENGINEERING-LOG.md

A narrative record of the real bugs, review findings, and design decisions from building this
project - reconstructed from the actual commit history (`git log`), which already documents each
finding in detail. Preserved here in full because it's good evidence of a rigorous review
process, not because [`ARCHITECTURE.md`](ARCHITECTURE.md) needs the history. That file stays a
clean, current-state design doc; this one is the "how we actually got there" story, in roughly
the order things happened.

## 1. Config hardening: no raw defaults in source code

Early on, `config.py`'s `Settings` fields (`database_url`, `embedding_model_name`,
`embedding_dimension`, `chunk_size`, `chunk_overlap`, `top_k`, `similarity_threshold`,
`bedrock_model_id`, `bedrock_region`, `prompt_template_version`) all had ordinary Python
defaults. This was flagged as exactly the kind of thing that quietly drifts from `.env.example`
and lets the app boot with an unnoticed, wrong default. Every field was made required (no
default at all) - `.env.example` became the single documented source, and a missing/
misconfigured setting is now a hard, immediate `pydantic.ValidationError` at import time.

One real gotcha this surfaced: pydantic-settings does not coerce an empty `.env` string to
`None` for a required `Optional[float]` field - it tries to parse `""` as a float and raises.
`SIMILARITY_THRESHOLD=` (intentionally empty, meaning "no threshold") needed a
`field_validator(mode="before")` mapping `""` to `None` before type validation runs. The same
validator was reused later for `LANGSMITH_API_KEY` when observability was added.

Validated at the time: `ruff` clean, `alembic upgrade head` against dockerized postgres, tests
passing, `docker compose build+up` healthy with `/health` OK, and - the actual proof the
hardening works - removing `.env` entirely correctly raises a `ValidationError` listing every
missing field.

## 2. The chunk_overlap blowup and parser exception-handling gaps

**Finding:** `RecursiveCharacterChunker` had no validation that `chunk_overlap` stayed sane
relative to `chunk_size` - a silent chunk-overlap blowup bug: nothing stopped `chunk_overlap`
from approaching or exceeding `chunk_size`, which could silently multiply chunk count (and
therefore embedding-call volume) during a parameter sweep with zero error signal.

**Fix:** the constructor now fails fast (`ValueError`) if `chunk_overlap > chunk_size / 2` or
either parameter is invalid, rather than silently degrading.

**Bundled in the same review pass**, two lower-severity exception-handling gaps in the parsers:
non-UTF-8 source files and oversized PDFs were previously left to raise raw stdlib exceptions
instead of a domain-specific one. Fixed with `ParserError`, raised for both non-UTF-8 files and
PDFs over a page-count guard (500 pages), instead of leaking raw exceptions out of the ingestion
boundary.

Both found and required by review before the step was allowed to merge; re-validated
independently afterward (ruff, full pytest suite against dockerized postgres).

## 3. Protocol/implementation separation becomes a hard rule

A later structural review found two conformance gaps against this project's own conventions:
`DocumentParser`/`Chunker` Protocols were living in the same files as their implementations
(`parser.py`/`chunker.py`) instead of a dedicated `protocols.py`, and the concrete classes
(`MarkdownParser`, `TextParser`, `PdfParser`, `RecursiveCharacterChunker`) satisfied their
Protocol only structurally (duck typing), with no explicit `class Foo(SomeProtocol):`
declaration anywhere.

Both were fixed - a single `ingestion/protocols.py` holds both Protocols (one file, since
ingestion covers both parsing and chunking as one package per the existing layout, mirroring the
one-protocol-file-per-package pattern used by `embeddings/`/`retrieval/`/`prompts/`/`llm/`
without over-fragmenting) - and the second finding was promoted to a hard rule in
`CODING-GUIDELINES.md`: every future Protocol/implementation pair must explicitly subclass its
Protocol, not just satisfy it structurally. This is plain PEP 544 behavior (no
`@runtime_checkable` needed) and doesn't change duck-typing behavior anywhere else - confirmed
by the full test suite passing unchanged after the subclassing was added everywhere.

## 4. Retrieval test isolation: a real, reproducible false-confidence bug

**Finding (High):** while reviewing `PgVectorRetriever` (which independently verified correct
via `EXPLAIN ANALYZE` that the HNSW index was actually used, not a sequential scan, and that the
score math and NULL-embedding handling were correct), the review process reproduced a real bug:
integration tests in `tests/integration/test_retrieval.py` were not isolated from unrelated data
in `document_chunks`. Seeding 20,000 unrelated random vectors into the table and rerunning the
suite failed 2 of 6 tests, because `PgVectorRetriever.search()` correctly searches the *whole*
table, unscoped, and several tests asserted exact top-K membership/ordering that silently
depended on the table being empty except for that test's own fixture data.

**Fix, two parts:**

1. `tests/integration/conftest.py`'s `db_session` fixture was rewritten to wrap every test in a
   transaction rolled back afterward via a per-test SAVEPOINT - this fixed
   `tests/integration/test_storage.py`'s identical latent issue for free, with no changes needed
   there.
2. A per-test rollback alone can't hide another already-committed session's rows (READ
   COMMITTED visibility), so `test_retrieval.py`'s assertions were also scoped to each fixture's
   own `document_id`.

**Verified, not just asserted:** reproduced the exact repro after the fix - seeded 20,000
unrelated rows again, reran the full suite green, and confirmed 0 residual rows after a full
test run.

## 5. A citation-injection test that proved nothing

**Finding (Medium):** this was the project's most security-sensitive component so far (the
prompt-injection surface in `prompts/v1.py`). Review verified the real implementation against a
genuine tag-breakout payload (correctly escaped, no extra tags produced) - but found the
adversarial *test* itself was weak: the original payload had no HTML metacharacters at all and
would pass identically even with `html.escape()` removed entirely. It proved nothing about
whether escaping actually worked.

**Fix:** replaced the payload with a real tag/attribute-breakout attempt (closing the current
`<document>` tag early and opening a fake new one, plus an embedded `"` in a document name to
test attribute-breakout).

**Verified via mutation testing:** temporarily removed `html.escape()`, confirmed the test now
fails, restored it, confirmed it passes again - concrete proof the test is meaningful. Also
confirmed both `document_name` and `content` are escaped with `quote=True` (not just content),
and captured `PromptBuilderV1.template_version` being just a hardcoded label (no real
content-tracking mechanism) as an open item for the future evaluation-runner step.

**Later, when the context-rendering logic was extracted out of `PromptBuilderV1` into a shared,
version-agnostic `prompts/rendering.py`** (so a future v2/v3 template couldn't copy-paste or
silently weaken this security-load-bearing escaping logic), the exact same mutation-testing
proof was re-run in the new location - stripped `escape()`, confirmed the test failed, restored,
confirmed it passed again - to confirm the security-relevant coverage survived the move intact.

## 6. Making EmbeddingModel.embed() async

Flagged as an open item since the embeddings step: `HuggingFaceEmbeddingModel.embed()` was a
plain synchronous method - correct on its own, but calling it directly from an `async def`
FastAPI handler would block the event loop for the full inference duration. Fixed by wrapping
the blocking `sentence-transformers` `.encode()` call in `asyncio.to_thread` internally,
matching `LocalLLMClient.generate()`'s existing pattern, so the public signature became
`async` and callers never need to think about threading themselves.

## 7. Conflating three different outcomes into one boolean

**Finding (Critical):** review ran three real questions through the actual retriever + prompt +
local LLM pipeline (not just unit tests) and found that `Answer.abstained: bool` collapsed three
genuinely different outcomes into the same label: the model correctly saying it doesn't have
enough information (true abstention), a correct-but-uncited answer (a citation-format-compliance
failure, not a correctness failure), and a hallucination-on-no-context case that also lacked
citations. All three produced `abstained=True` for unrelated reasons - directly corrupting the
abstention-accuracy and hallucination-count evaluation metrics this feature exists to support.

**Fix:** `Answer` gained a second, independent field, `citations_missing`. `abstained` now means
only "the answer text matched the documented abstention phrase family" - the explicit signal.
`citations_missing` means "zero valid citations and no phrase match" - the previously-ambiguous
case. Two plain booleans were chosen over a 3-way enum since the two conditions are genuinely
independent checks, not mutually exclusive states.

**Verified by re-running the same real end-to-end repro** after the fix, confirming the three
cases now come out distinguishable rather than all reporting `abstained=True`. A previously
missing test (`Citation.snippet`'s truncation branch) was also added in the same pass, and the
citation regex was confirmed tolerant of roughly a dozen realistic real-model formatting
variations - though the dominant failure mode turned out to be the local model not attempting
the citation format at all, not regex brittleness.

## 8. The local model's citation-compliance gap, confirmed again at the API level

When the first true end-to-end API test was written (`tests/integration/test_query_api.py` -
real Postgres, real embeddings, real retriever, real `LocalLLMClient`, real citation extraction,
hitting `POST /query` with no dependency overrides), the sub-step's original plan was to assert
an answerable question's response *must* include a citation marker. Before writing that
assertion, it was empirically checked first: the local model reliably omits citation markers
even when explicitly asked, across three different phrasings.

Rather than force a test to fit the original plan, the assertion was changed to match what's
actually true: the answerable-question case checks the answer content is factually correct plus
that `abstained`/`citations_missing` are validly typed (citations are checked *if* present, not
required); the no-relevant-content case checks `abstained OR citations_missing` is `True`. Real
example verified at the time: "What is the API rate limit?" produced a correct, grounded answer
citing the right fact in ~1.45s wall-clock - confirming the pipeline is genuinely functional
end-to-end even though citation-marker compliance is a known, separately-tracked local-model
limitation.

## 9. First baseline evaluation run

With the dataset (57 questions, 44 answerable/13 unanswerable, `evaluation/dataset/v1.jsonl`)
and seed corpus (11 documents) in place, the evaluation runner was run for the first time
against the full dataset. Results are recorded as current-state facts in
[`ARCHITECTURE.md`](ARCHITECTURE.md) section 12, not repeated here. Short version: 79.5% answer
correctness, 100% Recall@5, and 92.3% abstention accuracy all essentially met or met README's
targets. Groundedness came back 0% - a known, already-documented gap (see items 7-8 above): the
local model gives correct, well-retrieved answers but rarely emits the citation-marker format
this metric requires, which is exactly what `citations_missing` was built to surface honestly
rather than hide behind an inflated number.

No "change one variable, re-run, compare" experiment (the workflow in `ARCHITECTURE.md` section
3.3) has been run yet against this baseline - that remains a real, currently open item.

## 10. Seed service: extracting shared ingestion logic, and proving idempotency for real

By Step 15, ingestion logic (parse -> chunk -> embed -> persist) had been duplicated inline in
both `tests/integration/test_ingestion_flow.py` and `evaluation/runner.py`. This was extracted
into `ingestion/service.py`'s `ingest_document()`/`ingest_directory()` - idempotent per
`content_hash`, used by both the evaluation runner and the new `seed/seed.py` CLI.

One test-design subtlety worth recording: `test_ingestion_flow.py`'s content_hash-uniqueness
constraint test was deliberately *not* refactored onto the new shared `ingest_document()` -
since that function's own idempotency check skips *before* ever attempting a duplicate insert,
routing the test through it would mean the DB constraint it's meant to verify never actually
gets exercised. A separate `test_ingest_document_is_idempotent` test was added instead to cover
the function's own skip behavior, keeping the constraint test on its original raw-insert
approach.

`seed/seed.py` deliberately does not duplicate `evaluation/seed_docs/` into a second
`seed/documents/` directory - this project's only real content is the eval corpus, and a second
copy would silently drift from the first. Manual verification (real Postgres, real embedding
model): ran `seed/seed.py` against `evaluation/seed_docs/` twice. Run 1 (fresh DB): 11 files, 11
newly ingested, 34 chunks. Run 2 (immediately after): 11 files, 0 newly ingested, all 11
correctly reported as already-present - idempotency confirmed end-to-end, not just asserted.

## 11. Observability: verifying LangSmith is a genuine no-op when unconfigured

When optional LangSmith tracing was added (`@traceable` on
`RAGService.answer_question_with_trace`, via the standalone `langsmith` SDK - not LangChain,
which this project deliberately avoids), the claim that it's a safe no-op without an API key
wasn't just assumed from documentation: `@traceable`'s behavior was verified directly against
the installed package for both sync and async functions, confirming it checks
`LANGSMITH_TRACING`/`LANGCHAIN_TRACING_V2` env vars and makes no network calls and raises no
errors when they're unset. `config.py`'s `langsmith_api_key` field was also verified both ways -
removing it from a required-fields check correctly raises `ValidationError`, and a normal
empty/unset value correctly resolves to `None` rather than silently misbehaving.
