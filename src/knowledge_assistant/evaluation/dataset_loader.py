"""Loads evaluation/dataset/v1.jsonl into typed row objects.

Distinct from src/knowledge_assistant/evaluation/ (this package - eval CODE: loader, metrics,
runner) vs the top-level evaluation/ directory (eval DATA: seed docs + dataset file) - see
evaluation/dataset/README.md's "Layout choice" section for the full reasoning. This loader
reads from that top-level evaluation/dataset/ directory; it is not itself where the data lives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# src/knowledge_assistant/evaluation/dataset_loader.py -> repo root is 3 levels up.
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_PATH = _REPO_ROOT / "evaluation" / "dataset" / "v1.jsonl"
SEED_DOCS_DIR = _REPO_ROOT / "evaluation" / "seed_docs"


@dataclass(frozen=True, slots=True)
class EvalRow:
    """One row of the evaluation dataset - see evaluation/dataset/README.md for the field
    semantics (in particular: expected_answer is the literal sentinel "ABSTAIN" for
    unanswerable rows, not free text)."""

    id: str
    question: str
    category: str  # "answerable" | "unanswerable"
    expected_answer: str
    expected_sources: list[str]


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> list[EvalRow]:
    """Reads a JSONL dataset file into EvalRow objects, in file order."""
    rows: list[EvalRow] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            rows.append(EvalRow(**data))
    return rows
