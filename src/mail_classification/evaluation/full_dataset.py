"""Fail-fast enforcement of the approved Full-dataset input contract.

Fold generation and model training must never run against Full data that
does not match the human-reviewed hash recorded in the tracked approval
decision (``docs/reviews/full_review_decision.json``). That decision file,
not a literal in code, is the single source of truth: it is updated in
lockstep whenever a new Full generation is reviewed and approved.
"""

from __future__ import annotations

import json
from pathlib import Path

from mail_classification.generation.io import read_jsonl
from mail_classification.schemas import RawMailRecord, sha256_file


def approved_full_data_hash(decision_path: str | Path) -> str:
    """Read the approved Full-dataset hash from the tracked review decision."""
    path = Path(decision_path)
    if not path.is_file():
        raise ValueError(f"tracked Full approval decision is missing: {path}")
    decision = json.loads(path.read_text(encoding="utf-8"))
    if "full_data_hash" not in decision:
        raise ValueError(f"{path} is missing required field: full_data_hash")
    return decision["full_data_hash"]


def verify_full_dataset_hash(
    data_path: str | Path, decision_path: str | Path
) -> str:
    """Fail fast unless the exact bytes at ``data_path`` match the approved hash."""
    data_path = Path(data_path)
    if not data_path.is_file():
        raise ValueError(f"Full dataset is missing: {data_path}")
    expected_hash = approved_full_data_hash(decision_path)
    actual_hash = sha256_file(data_path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"Full dataset hash mismatch at {data_path}: "
            f"expected {expected_hash} (per {decision_path}), got {actual_hash}"
        )
    return actual_hash


def load_verified_full_dataset(
    data_path: str | Path, decision_path: str | Path
) -> list[RawMailRecord]:
    """Load the Full dataset, refusing to proceed unless its hash is approved."""
    verify_full_dataset_hash(data_path, decision_path)
    return read_jsonl(data_path)
