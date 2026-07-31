"""Phase 6 MinHashLSH Extension run orchestration; never touches Core artifacts.

Writes under outputs/extensions/ (not outputs/runs/ or outputs/data_quality/,
which are Core's namespace) and does not read or modify any Core output.
"""

from __future__ import annotations

from datetime import datetime, timezone
import platform
from pathlib import Path

from mail_classification.generation.io import write_csv, write_json
from mail_classification.generation.pipeline import _git_dirty, _git_value
from mail_classification.schemas import RawMailRecord, RunManifest

from .minhash import (
    DEFAULT_BANDS,
    DEFAULT_NUM_PERM,
    DEFAULT_SEED,
    DEFAULT_SHINGLE_SIZE,
    DEFAULT_THRESHOLD,
    NEAR_DUPLICATE_FIELDS,
    find_near_duplicates,
    summarize_near_duplicates,
)


def run_and_write_minhash_extension(
    records: list[RawMailRecord],
    data_hash: str,
    project_root: str | Path,
    *,
    run_id: str | None = None,
    shingle_size: int = DEFAULT_SHINGLE_SIZE,
    num_perm: int = DEFAULT_NUM_PERM,
    bands: int = DEFAULT_BANDS,
    threshold: float = DEFAULT_THRESHOLD,
    seed: int = DEFAULT_SEED,
) -> Path:
    project_root = Path(project_root).resolve()
    rows = find_near_duplicates(
        records,
        shingle_size=shingle_size,
        num_perm=num_perm,
        bands=bands,
        threshold=threshold,
        seed=seed,
    )
    summary = summarize_near_duplicates(rows)

    resolved_run_id = run_id or f"phase6-minhash-seed{seed}"
    run_dir = project_root / "outputs" / "extensions" / resolved_run_id
    write_csv(run_dir / "near_duplicates.csv", rows, NEAR_DUPLICATE_FIELDS)
    write_json(run_dir / "summary.json", summary)

    manifest = RunManifest(
        run_id=resolved_run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=["run_and_write_minhash_extension"],
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependency_versions={},
        config_path=None,
        config_hash=None,
        data_path=None,
        data_hash=data_hash,
        data_generation_seed=None,
        template_path=None,
        template_hash=None,
        generator_version=None,
        approval_decision_path=None,
        approval_decision_hash=None,
        cv_seed=seed,
        fold_artifact_path=None,
        fold_artifact_hash=None,
        preprocessor_name=None,
        preprocessor_version=None,
        model_name=None,
        model_parameters={
            "shingle_size": shingle_size,
            "num_perm": num_perm,
            "bands": bands,
            "threshold": threshold,
        },
        primary_metric="jaccard_similarity",
        output_directory=str(run_dir),
    )
    write_json(run_dir / "manifest.json", manifest.model_dump(mode="json"))
    return run_dir
