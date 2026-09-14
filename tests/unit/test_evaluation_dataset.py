"""Data-integrity tests for the evaluation dataset (evaluation/dataset/v1.jsonl) and the seed
docs it references (evaluation/seed_docs/). Pure data validation - no RAG pipeline, no model,
no DB. The evaluation runner that actually scores answers against this dataset lives
separately (evaluation/runner.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATASET_PATH = _REPO_ROOT / "evaluation" / "dataset" / "v1.jsonl"
_SEED_DOCS_DIR = _REPO_ROOT / "evaluation" / "seed_docs"

_REQUIRED_FIELDS = {"id", "question", "category", "expected_answer", "expected_sources"}
_ALLOWED_CATEGORIES = {"answerable", "unanswerable"}


def _load_dataset() -> list[dict[str, Any]]:
    rows = []
    with _DATASET_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@pytest.fixture(scope="module")
def dataset() -> list[dict[str, Any]]:
    return _load_dataset()


@pytest.fixture(scope="module")
def seed_doc_filenames() -> set[str]:
    return {path.name for path in _SEED_DOCS_DIR.glob("*.md")}


@pytest.mark.unit
def test_dataset_file_is_valid_jsonl() -> None:
    # _load_dataset() itself calls json.loads() per line - if any line were malformed this
    # fixture/helper would already have raised. Re-verify explicitly here so a parse failure
    # is reported as this test failing, not an opaque fixture-setup error in every other test.
    rows = _load_dataset()
    assert len(rows) > 0


@pytest.mark.unit
def test_dataset_has_meaningfully_more_than_the_original_baseline(
    dataset: list[dict[str, Any]],
) -> None:
    # README.md's original success target was 20-30 questions; this dataset is deliberately
    # larger per the approved task.
    assert len(dataset) >= 50


@pytest.mark.unit
def test_every_row_has_required_fields(dataset: list[dict[str, Any]]) -> None:
    for row in dataset:
        missing = _REQUIRED_FIELDS - row.keys()
        assert not missing, f"{row.get('id', '?')} missing fields: {missing}"


@pytest.mark.unit
def test_every_row_has_a_unique_id(dataset: list[dict[str, Any]]) -> None:
    ids = [row["id"] for row in dataset]
    assert len(ids) == len(set(ids))


@pytest.mark.unit
def test_no_duplicate_questions(dataset: list[dict[str, Any]]) -> None:
    questions = [row["question"] for row in dataset]
    assert len(questions) == len(set(questions))


@pytest.mark.unit
def test_category_is_one_of_the_two_allowed_values(dataset: list[dict[str, Any]]) -> None:
    for row in dataset:
        assert row["category"] in _ALLOWED_CATEGORIES, (
            f"{row['id']} has invalid category: {row['category']!r}"
        )


@pytest.mark.unit
def test_unanswerable_rows_have_empty_expected_sources(dataset: list[dict[str, Any]]) -> None:
    for row in dataset:
        if row["category"] == "unanswerable":
            assert row["expected_sources"] == [], f"{row['id']} should have no expected sources"


@pytest.mark.unit
def test_unanswerable_rows_use_the_abstain_sentinel(dataset: list[dict[str, Any]]) -> None:
    for row in dataset:
        if row["category"] == "unanswerable":
            assert row["expected_answer"] == "ABSTAIN", (
                f"{row['id']}: unanswerable rows must use the documented ABSTAIN sentinel"
            )


@pytest.mark.unit
def test_answerable_rows_have_at_least_one_expected_source(dataset: list[dict[str, Any]]) -> None:
    for row in dataset:
        if row["category"] == "answerable":
            assert len(row["expected_sources"]) >= 1, f"{row['id']} has no expected_sources"


@pytest.mark.unit
def test_expected_sources_reference_real_seed_doc_files(
    dataset: list[dict[str, Any]], seed_doc_filenames: set[str]
) -> None:
    for row in dataset:
        for source in row["expected_sources"]:
            assert source in seed_doc_filenames, (
                f"{row['id']} references {source!r}, not found in evaluation/seed_docs/"
            )


@pytest.mark.unit
def test_seed_docs_directory_is_not_empty() -> None:
    assert len(list(_SEED_DOCS_DIR.glob("*.md"))) >= 8
