"""Aggregate evaluation report: per-metric scores across a dataset run, plus the exact config
values used to produce them - per docs/ARCHITECTURE.md section 3.3's "change one variable,
re-run, compare" workflow, a report is only useful for comparison if it records what config
(chunk size, top-K, embedding model, ...) it was run with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from knowledge_assistant.config import settings
from knowledge_assistant.evaluation.dataset_loader import EvalRow
from knowledge_assistant.rag_service import QueryTrace

# Local inference has no meaningful per-token price - there's no API bill for running a model
# on your own CPU. This is a placeholder, not a real cost calculation: it becomes meaningful
# once/if a Bedrock LLMClient is implemented and configured with real per-token pricing for
# whichever model is selected.
_COST_NOTE_LOCAL = (
    "llm_provider=local: no real per-token cost - local CPU inference has no API bill. "
    "Token counts are still recorded below for when a priced provider (e.g. Bedrock) is used."
)


@dataclass(frozen=True, slots=True)
class RowResult:
    """Per-question scoring detail - kept alongside the aggregate report so a low aggregate
    score can be traced back to which specific questions failed."""

    row: EvalRow
    trace: QueryTrace
    correctness: bool | None  # answerable rows only
    retrieval_hit: bool | None  # answerable rows only
    grounded: bool | None  # answerable rows only
    abstention_correct: bool | None  # unanswerable rows only


@dataclass(frozen=True, slots=True)
class EvalReport:
    dataset_version: str
    run_at: str
    num_questions: int
    num_answerable: int
    num_unanswerable: int

    # Config the run was made with - see docs/ARCHITECTURE.md section 3.3.
    chunk_size: int
    chunk_overlap: int
    top_k: int
    similarity_threshold: float | None
    embedding_model_name: str
    llm_provider: str
    local_llm_model_name: str
    prompt_template_version: str

    answer_correctness_pct: float
    recall_at_k_pct: float
    groundedness_pct: float
    abstention_accuracy_pct: float
    avg_retrieval_latency_ms: float
    avg_total_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    cost_note: str

    row_results: list[RowResult] = field(repr=False)


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(100 * numerator / denominator, 1)


def build_report(dataset_version: str, row_results: list[RowResult]) -> EvalReport:
    answerable = [r for r in row_results if r.row.category == "answerable"]
    unanswerable = [r for r in row_results if r.row.category == "unanswerable"]

    correctness_hits = sum(1 for r in answerable if r.correctness)
    retrieval_hits = sum(1 for r in answerable if r.retrieval_hit)
    grounded_hits = sum(1 for r in answerable if r.grounded)
    abstention_hits = sum(1 for r in unanswerable if r.abstention_correct)

    all_traces = [r.trace for r in row_results]
    avg_retrieval_latency_ms = (
        sum(t.retrieval_latency_ms for t in all_traces) / len(all_traces) if all_traces else 0.0
    )
    avg_total_latency_ms = (
        sum(t.total_latency_ms for t in all_traces) / len(all_traces) if all_traces else 0.0
    )
    total_input_tokens = sum(t.llm_response.input_tokens for t in all_traces)
    total_output_tokens = sum(t.llm_response.output_tokens for t in all_traces)

    return EvalReport(
        dataset_version=dataset_version,
        run_at=datetime.now(UTC).isoformat(),
        num_questions=len(row_results),
        num_answerable=len(answerable),
        num_unanswerable=len(unanswerable),
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        top_k=settings.top_k,
        similarity_threshold=settings.similarity_threshold,
        embedding_model_name=settings.embedding_model_name,
        llm_provider=settings.llm_provider,
        local_llm_model_name=settings.local_llm_model_name,
        prompt_template_version=settings.prompt_template_version,
        answer_correctness_pct=_pct(correctness_hits, len(answerable)),
        recall_at_k_pct=_pct(retrieval_hits, len(answerable)),
        groundedness_pct=_pct(grounded_hits, len(answerable)),
        abstention_accuracy_pct=_pct(abstention_hits, len(unanswerable)),
        avg_retrieval_latency_ms=round(avg_retrieval_latency_ms, 1),
        avg_total_latency_ms=round(avg_total_latency_ms, 1),
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost_usd=0.0,
        cost_note=_COST_NOTE_LOCAL,
        row_results=row_results,
    )


def render_markdown(report: EvalReport) -> str:
    lines = [
        f"# Evaluation Report - dataset {report.dataset_version}",
        "",
        f"Run at: {report.run_at}",
        (
            f"Questions: {report.num_questions} "
            f"({report.num_answerable} answerable, {report.num_unanswerable} unanswerable)"
        ),
        "",
        "## Config",
        "",
        f"- chunk_size: {report.chunk_size}",
        f"- chunk_overlap: {report.chunk_overlap}",
        f"- top_k: {report.top_k}",
        f"- similarity_threshold: {report.similarity_threshold}",
        f"- embedding_model_name: {report.embedding_model_name}",
        f"- llm_provider: {report.llm_provider}",
        f"- local_llm_model_name: {report.local_llm_model_name}",
        f"- prompt_template_version: {report.prompt_template_version}",
        "",
        "## Metrics",
        "",
        (
            f"- Answer correctness: {report.answer_correctness_pct}% "
            f"(answerable questions, keyword-overlap heuristic)"
        ),
        f"- Recall@{report.top_k} (source hit rate): {report.recall_at_k_pct}%",
        (
            f"- Groundedness: {report.groundedness_pct}% "
            f"(citation actually references the expected source)"
        ),
        (
            f"- Abstention accuracy: {report.abstention_accuracy_pct}% "
            f"(unanswerable questions, abstained OR citations_missing)"
        ),
        f"- Avg retrieval latency: {report.avg_retrieval_latency_ms} ms",
        f"- Avg total latency: {report.avg_total_latency_ms} ms",
        f"- Total tokens: {report.total_input_tokens} in / {report.total_output_tokens} out",
        f"- Estimated cost: ${report.estimated_cost_usd:.4f} ({report.cost_note})",
        "",
        "## Per-question results",
        "",
        ("| id | category | correct | retrieval_hit | grounded | abstention_correct | total_ms |"),
        "|---|---|---|---|---|---|---|",
    ]
    for r in report.row_results:
        lines.append(
            f"| {r.row.id} | {r.row.category} | {r.correctness} | {r.retrieval_hit} | "
            f"{r.grounded} | {r.abstention_correct} | {r.trace.total_latency_ms:.0f} |"
        )
    return "\n".join(lines) + "\n"


def render_summary(report: EvalReport) -> str:
    """Short, printable summary for a terminal run - the markdown report has the full detail."""
    return (
        f"Evaluation report ({report.dataset_version}, {report.num_questions} questions, "
        f"run at {report.run_at})\n"
        f"  answer correctness:  {report.answer_correctness_pct}%\n"
        f"  recall@{report.top_k}:            {report.recall_at_k_pct}%\n"
        f"  groundedness:        {report.groundedness_pct}%\n"
        f"  abstention accuracy: {report.abstention_accuracy_pct}%\n"
        f"  avg retrieval ms:    {report.avg_retrieval_latency_ms}\n"
        f"  avg total ms:        {report.avg_total_latency_ms}\n"
        f"  tokens in/out:       {report.total_input_tokens}/{report.total_output_tokens}\n"
        f"  estimated cost:      ${report.estimated_cost_usd:.4f} ({report.cost_note})"
    )
