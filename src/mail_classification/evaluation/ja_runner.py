"""Japanese counterpart of ``runner.py``.

Orchestration is identical; only the condition-cell runner (``ja_cv``
instead of ``cv``), default condition tuple (J0-JC instead of D0-D2),
run-ID prefix (``phaseJA4-*``), and manifest dependency versions differ.
``metrics.py``/``aggregate.py``/``paired.py`` are reused unmodified: they
operate on generic dict rows and duck-typed ``FoldFitResult``-shaped
objects, with no English-specific assumptions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform

from mail_classification.generation.io import write_csv, write_json
from mail_classification.generation.pipeline import _git_dirty, _git_value
from mail_classification.schemas import FoldArtifact, RawMailRecord, RunManifest, sha256_file

from .aggregate import METRICS_SUMMARY_FIELDS, build_metrics_summary
from .ja_cv import run_core_experiments
from .metrics import (
    CONFUSION_FIELDS,
    METRICS_LONG_FIELDS,
    build_confusion_matrix_rows,
    build_metrics_long,
)
from .paired import PAIRED_DIFFERENCE_FIELDS, build_paired_differences

OOF_FIELDS = ["sample_id", "condition", "model", "fold_id", "true_label", "predicted_label"]


def load_fold_artifact(path: str | Path) -> FoldArtifact:
    """Load and re-validate the shared Fold artifact written by ``write_fold_artifact``."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return FoldArtifact.model_validate(payload)


def run_and_write_core_experiments(
    records: list[RawMailRecord],
    fold_artifact_path: str | Path,
    project_root: str | Path,
    *,
    conditions: tuple[str, ...] = ("J0", "J1", "J2", "JC"),
    models: tuple[str, ...] = ("linear_svc", "logistic_regression"),
    run_id: str | None = None,
    baseline_condition: str = "J0",
) -> Path:
    """Run every Core cell, write all Phase JA-4 artifacts, return the run directory."""
    project_root = Path(project_root).resolve()
    fold_artifact_path = Path(fold_artifact_path)
    fold_artifact = load_fold_artifact(fold_artifact_path)

    fold_results = run_core_experiments(
        records, fold_artifact, conditions=conditions, models=models
    )
    metrics_long = build_metrics_long(fold_results)
    metrics_summary = build_metrics_summary(metrics_long)
    confusion_rows = build_confusion_matrix_rows(fold_results)
    paired_rows = build_paired_differences(
        metrics_long, baseline_condition=baseline_condition
    )
    oof_rows = [
        {
            "sample_id": row["sample_id"],
            "condition": result.condition,
            "model": result.model,
            "fold_id": result.fold_id,
            "true_label": row["true_label"],
            "predicted_label": row["predicted_label"],
        }
        for result in fold_results
        for row in result.oof_rows
    ]

    resolved_run_id = run_id or f"phaseJA4-core-seed{fold_artifact.metadata.random_seed}"
    run_dir = project_root / "outputs" / "runs" / resolved_run_id
    write_csv(run_dir / "metrics_long.csv", metrics_long, METRICS_LONG_FIELDS)
    write_csv(run_dir / "metrics_summary.csv", metrics_summary, METRICS_SUMMARY_FIELDS)
    write_csv(run_dir / "predictions_oof.csv", oof_rows, OOF_FIELDS)
    write_csv(run_dir / "confusion_matrix.csv", confusion_rows, CONFUSION_FIELDS)
    write_csv(run_dir / "paired_differences.csv", paired_rows, PAIRED_DIFFERENCE_FIELDS)

    manifest = RunManifest(
        run_id=resolved_run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=["run_core_experiments_ja", *conditions, *models],
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependency_versions={
            package: version(package)
            for package in ("scikit-learn", "pydantic", "sudachipy", "sudachidict-core", "neologdn")
        },
        config_path=None,
        config_hash=None,
        data_path=None,
        data_hash=fold_artifact.metadata.data_hash,
        data_generation_seed=None,
        template_path=None,
        template_hash=None,
        generator_version=None,
        approval_decision_path=None,
        approval_decision_hash=None,
        cv_seed=fold_artifact.metadata.random_seed,
        fold_artifact_path=str(fold_artifact_path),
        fold_artifact_hash=sha256_file(fold_artifact_path),
        preprocessor_name="japanese_minimal",
        preprocessor_version="1.0.0",
        model_name=None,
        model_parameters=None,
        primary_metric="macro_f1",
        output_directory=str(run_dir),
    )
    write_json(run_dir / "manifest.json", manifest.model_dump(mode="json"))
    return run_dir
