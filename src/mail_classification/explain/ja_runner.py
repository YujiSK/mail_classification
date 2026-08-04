"""Japanese counterpart of ``runner.py`` (explainability orchestration).

Consumes Phase JA-4's already-written ``predictions_oof.csv`` rather than
recomputing OOF, so the explained errors are traceably the exact
predictions that were evaluated.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from importlib.metadata import version
import platform
from pathlib import Path

from mail_classification.evaluation.runner import load_fold_artifact
from mail_classification.generation.io import write_csv, write_json
from mail_classification.generation.pipeline import _git_dirty, _git_value
from mail_classification.models import apply_condition_preprocessing_ja
from mail_classification.schemas import RawMailRecord, RunManifest, sha256_file

from .ja_errors import (
    ERROR_CATEGORY_COUNTS_FIELDS,
    ERROR_CATEGORY_SUMMARY_FIELDS,
    MISCLASSIFICATION_FIELDS,
    build_misclassification_rows_ja,
    summarize_error_categories,
    summarize_error_category_counts,
)
from .ja_evidence import enrich_misclassifications_with_evidence
from .ja_linear import (
    COEFFICIENT_FIELDS,
    DESCRIPTIVE_COEFFICIENT_FIELDS,
    audit_top_features_for_structural_artifacts,
    extract_descriptive_full_fit_coefficients,
    extract_fold_coefficients,
)


def read_oof_predictions(path: str | Path) -> list[dict[str, object]]:
    """Read a Phase JA-4 predictions_oof.csv back into typed dict rows."""
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["fold_id"] = int(row["fold_id"])
    return rows


def run_and_write_explainability(
    records: list[RawMailRecord],
    fold_artifact_path: str | Path,
    oof_predictions_path: str | Path,
    project_root: str | Path,
    *,
    conditions: tuple[str, ...] = ("J0", "J1", "J2", "JC"),
    models: tuple[str, ...] = ("linear_svc", "logistic_regression"),
    run_id: str | None = None,
    top_n: int = 15,
) -> Path:
    """Extract Fold/descriptive coefficients and OOF misclassifications; write all artifacts."""
    project_root = Path(project_root).resolve()
    fold_artifact_path = Path(fold_artifact_path)
    fold_artifact = load_fold_artifact(fold_artifact_path)
    records_by_id = {record.id: record for record in records}

    fold_coefficient_rows: list[dict[str, object]] = []
    descriptive_rows: list[dict[str, object]] = []
    processed_text_by_condition_and_id: dict[tuple[str, str], str] = {}
    for condition_name in conditions:
        processed = apply_condition_preprocessing_ja(
            condition_name, [record.raw_text for record in records]
        )
        for record, text in zip(records, processed):
            processed_text_by_condition_and_id[(condition_name, record.id)] = text
        for model_name in models:
            fold_coefficient_rows.extend(
                extract_fold_coefficients(
                    records, fold_artifact, condition_name, model_name, top_n=top_n
                )
            )
            descriptive_rows.extend(
                extract_descriptive_full_fit_coefficients(
                    records, condition_name, model_name, top_n=top_n
                )
            )
    structural_audit_rows = audit_top_features_for_structural_artifacts(
        fold_coefficient_rows
    )

    oof_rows = read_oof_predictions(oof_predictions_path)
    relevant_oof_rows = [
        row
        for row in oof_rows
        if row["condition"] in conditions and row["model"] in models
    ]
    misclassification_rows = build_misclassification_rows_ja(
        relevant_oof_rows, records_by_id, processed_text_by_condition_and_id
    )
    misclassification_rows = enrich_misclassifications_with_evidence(
        misclassification_rows, records, fold_artifact
    )
    error_summary_rows = summarize_error_categories(misclassification_rows)
    error_category_counts_rows = summarize_error_category_counts(misclassification_rows)

    resolved_run_id = run_id or f"phaseJA5-explain-seed{fold_artifact.metadata.random_seed}"
    run_dir = project_root / "outputs" / "runs" / resolved_run_id
    write_csv(run_dir / "fold_coefficients.csv", fold_coefficient_rows, COEFFICIENT_FIELDS)
    write_csv(
        run_dir / "descriptive_full_fit_coefficients.csv",
        descriptive_rows,
        DESCRIPTIVE_COEFFICIENT_FIELDS,
    )
    write_csv(
        run_dir / "structural_artifact_audit.csv", structural_audit_rows, COEFFICIENT_FIELDS
    )
    write_csv(
        run_dir / "misclassifications_ja.csv", misclassification_rows, MISCLASSIFICATION_FIELDS
    )
    write_csv(
        run_dir / "error_category_summary.csv",
        error_summary_rows,
        ERROR_CATEGORY_SUMMARY_FIELDS,
    )
    write_csv(
        run_dir / "error_category_counts.csv",
        error_category_counts_rows,
        ERROR_CATEGORY_COUNTS_FIELDS,
    )

    manifest = RunManifest(
        run_id=resolved_run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=["run_and_write_explainability_ja", *conditions, *models],
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
