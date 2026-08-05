"""Subtopic-contamination Extension run orchestration.

Writes only under ``outputs/extensions/<run_id>/`` and
``data/derived/subtopic_contamination/<run_id>/`` -- never touches Core's
``outputs/runs/``, ``outputs/data_quality/``, ``outputs/folds/``, or
``data/raw/``. Reuses the exact common Fold artifact Core already produced
(``fold_artifact_path``), so every contamination level is evaluated on the
same train/validation split as Core, per sample_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import platform
from pathlib import Path

from mail_classification.evaluation.runner import load_fold_artifact
from mail_classification.explain.evidence import EVIDENCE_FIELDS, enrich_misclassifications_with_evidence
from mail_classification.generation.io import write_csv, write_json
from mail_classification.generation.pipeline import _git_dirty, _git_value
from mail_classification.schemas import RawMailRecord, RunManifest, sha256_file

from .analysis import (
    MAIN_SUBTOPIC_PAIR_SUMMARY_FIELDS,
    MISCLASSIFICATION_FIELDS,
    TRANSITION_SUMMARY_FIELDS,
    build_main_subtopic_pair_summary,
    build_misclassification_rows,
    build_transition_summary,
)
from .assignment import CONTAMINATION_LEVELS, build_contamination_assignment
from .cv import CELLS, run_all_cells
from .dataset import build_condition_records, write_condition_datasets
from .explain import (
    FEATURE_SHIFT_FIELDS,
    REPRESENTATIVE_EXAMPLE_FIELDS,
    build_feature_shift,
    build_representative_transition_examples,
)
from .metrics import (
    CONFUSION_FIELDS,
    METRICS_LONG_FIELDS,
    METRICS_SUMMARY_FIELDS,
    OOF_FIELDS,
    build_confusion_matrix_rows_by_level,
    build_metrics_long_by_level,
    build_metrics_summary_by_level,
    build_oof_rows_by_level,
)
from .paired import PAIRED_DIFFERENCE_FIELDS, build_paired_differences_vs_c0
from .quality import (
    CONDITION_STATISTICS_FIELDS,
    REVIEW_SAMPLE_FIELDS,
    audit_sentence_usage_skew,
    build_condition_statistics,
    build_review_samples,
)
from .stats import mcnemar_test, paired_bootstrap_macro_f1_diff

DEFAULT_RUN_ID = "phase-subtopic-contamination-seed42"
PRIMARY_CONDITION = "D1"
PRIMARY_MODEL = "linear_svc"

MISCLASSIFICATION_FIELDS_WITH_EVIDENCE = [*MISCLASSIFICATION_FIELDS, *EVIDENCE_FIELDS]


def run_and_write_subtopic_contamination_extension(
    full_records: list[RawMailRecord],
    fold_artifact_path: str | Path,
    project_root: str | Path,
    *,
    run_id: str = DEFAULT_RUN_ID,
    seed: int = 42,
) -> Path:
    project_root = Path(project_root).resolve()
    fold_artifact_path = Path(fold_artifact_path)
    fold_artifact = load_fold_artifact(fold_artifact_path)
    output_dir = project_root / "outputs" / "extensions" / run_id

    # 1. Deterministic assignment + four materialized datasets.
    assignment = build_contamination_assignment(full_records, seed=seed)
    assignment_dicts = [row.as_dict() for row in assignment]
    dataset_results, dataset_manifest_path = write_condition_datasets(
        full_records, assignment, project_root, run_id=run_id, output_dir=output_dir, seed=seed
    )
    records_by_level: dict[str, list[RawMailRecord]] = {
        level: build_condition_records(full_records, assignment, level) for level in CONTAMINATION_LEVELS
    }
    original_records_by_id = {record.id: record for record in full_records}

    # 2. Quality/leakage audits per condition.
    condition_statistics_rows: list[dict[str, object]] = []
    for level in CONTAMINATION_LEVELS:
        condition_statistics_rows.extend(
            build_condition_statistics(level, records_by_level[level], assignment)
        )
    write_csv(output_dir / "condition_statistics.csv", condition_statistics_rows, CONDITION_STATISTICS_FIELDS)

    sentence_usage_skew = [
        finding for level in CONTAMINATION_LEVELS for finding in audit_sentence_usage_skew(assignment, level)
    ]

    contaminated_records_by_id = {record.id: record for record in records_by_level["C30"]}
    review_samples = build_review_samples(assignment, contaminated_records_by_id, original_records_by_id)
    write_csv(output_dir / "review_samples.csv", review_samples, REVIEW_SAMPLE_FIELDS)

    # 3. CV experiments: 4 (condition, model) cells x 4 contamination levels, common Fold artifact.
    fold_results_by_level = run_all_cells(records_by_level, fold_artifact, cells=CELLS)
    metrics_long = build_metrics_long_by_level(fold_results_by_level)
    metrics_summary = build_metrics_summary_by_level(metrics_long)
    confusion_rows = build_confusion_matrix_rows_by_level(fold_results_by_level)
    oof_rows = build_oof_rows_by_level(fold_results_by_level)
    paired_differences = build_paired_differences_vs_c0(metrics_long)

    write_csv(output_dir / "metrics_long.csv", metrics_long, METRICS_LONG_FIELDS)
    write_csv(output_dir / "metrics_summary.csv", metrics_summary, METRICS_SUMMARY_FIELDS)
    write_csv(output_dir / "predictions_oof.csv", oof_rows, OOF_FIELDS)
    write_csv(output_dir / "confusion_matrix.csv", confusion_rows, CONFUSION_FIELDS)
    write_csv(output_dir / "paired_differences.csv", paired_differences, PAIRED_DIFFERENCE_FIELDS)

    # 4. Error transition / main x subtopic pair / misclassification analysis.
    transition_summary = build_transition_summary(oof_rows, assignment_dicts)
    main_subtopic_pair_summary = build_main_subtopic_pair_summary(oof_rows, assignment_dicts)
    write_csv(output_dir / "transition_summary.csv", transition_summary, TRANSITION_SUMMARY_FIELDS)
    write_csv(
        output_dir / "main_subtopic_pair_summary.csv",
        main_subtopic_pair_summary,
        MAIN_SUBTOPIC_PAIR_SUMMARY_FIELDS,
    )

    misclassifications = build_misclassification_rows(oof_rows, assignment_dicts, original_records_by_id)
    enriched_misclassifications: list[dict[str, object]] = []
    for level in CONTAMINATION_LEVELS:
        level_rows = [row for row in misclassifications if row["contamination_level"] == level]
        if not level_rows:
            continue
        enriched_misclassifications.extend(
            enrich_misclassifications_with_evidence(level_rows, records_by_level[level], fold_artifact)
        )
    write_csv(
        output_dir / "misclassifications.csv",
        enriched_misclassifications,
        MISCLASSIFICATION_FIELDS_WITH_EVIDENCE,
    )

    # 5. Explainability: LinearSVC feature shift + representative before/after examples.
    feature_shift = build_feature_shift(
        records_by_level, fold_artifact, condition_name=PRIMARY_CONDITION, model_name=PRIMARY_MODEL
    )
    write_csv(output_dir / "feature_shift.csv", feature_shift, FEATURE_SHIFT_FIELDS)

    representative_examples = build_representative_transition_examples(
        records_by_level, fold_artifact, assignment_dicts, condition_name=PRIMARY_CONDITION, model_name=PRIMARY_MODEL
    )
    write_csv(
        output_dir / "representative_transition_examples.csv",
        representative_examples,
        REPRESENTATIVE_EXAMPLE_FIELDS,
    )

    # 6. Statistical treatment (paired design; primary cell only, per project_rules.md
    #    section 8's "CV Foldを独立標本とした安易な有意差検定をしない").
    statistical_tests: dict[str, object] = {"mcnemar": [], "paired_bootstrap": []}
    for compare_level in ("C10", "C20", "C30"):
        for contaminated_only in (False, True):
            statistical_tests["mcnemar"].append(
                mcnemar_test(
                    oof_rows,
                    assignment_dicts,
                    condition=PRIMARY_CONDITION,
                    model=PRIMARY_MODEL,
                    compare_level=compare_level,
                    contaminated_only=contaminated_only,
                )
            )
        statistical_tests["paired_bootstrap"].append(
            paired_bootstrap_macro_f1_diff(
                oof_rows, condition=PRIMARY_CONDITION, model=PRIMARY_MODEL, compare_level=compare_level, seed=seed
            )
        )
    write_json(output_dir / "statistical_tests.json", statistical_tests)

    # 7. Headline summary.json (Phase 6 Extension precedent).
    summary_metrics = {
        level: {
            row["metric"]: row["cv_mean"]
            for row in metrics_summary
            if row["contamination_level"] == level
            and row["condition"] == PRIMARY_CONDITION
            and row["model"] == PRIMARY_MODEL
        }
        for level in CONTAMINATION_LEVELS
    }
    write_json(
        output_dir / "summary.json",
        {
            "primary_cell": {"condition": PRIMARY_CONDITION, "model": PRIMARY_MODEL},
            "contamination_counts": {
                result.level: result.contaminated_count for result in dataset_results
            },
            "primary_cell_macro_f1_by_level": {
                level: summary_metrics[level].get("macro_f1") for level in CONTAMINATION_LEVELS
            },
            "primary_cell_accuracy_by_level": {
                level: summary_metrics[level].get("accuracy") for level in CONTAMINATION_LEVELS
            },
            "sentence_usage_skew_findings": len(sentence_usage_skew),
            "review_sample_count": len(review_samples),
        },
    )
    if sentence_usage_skew:
        write_json(output_dir / "sentence_usage_skew.json", {"findings": sentence_usage_skew})

    # 8. Run manifest.
    c0_hash = next(result.data_hash for result in dataset_results if result.level == "C0")
    manifest = RunManifest(
        run_id=run_id,
        created_at=datetime.now(timezone.utc),
        git_commit=_git_value(project_root, "rev-parse", "HEAD"),
        git_dirty=_git_dirty(project_root),
        command=["run_and_write_subtopic_contamination_extension"],
        python_version=platform.python_version(),
        platform=platform.platform(),
        dependency_versions={package: version(package) for package in ("scikit-learn", "pydantic")},
        config_path=None,
        config_hash=None,
        data_path=str(dataset_manifest_path.relative_to(project_root)),
        data_hash=c0_hash,
        data_generation_seed=None,
        template_path=None,
        template_hash=None,
        generator_version=None,
        approval_decision_path=None,
        approval_decision_hash=None,
        cv_seed=seed,
        fold_artifact_path=str(fold_artifact_path),
        fold_artifact_hash=sha256_file(fold_artifact_path),
        preprocessor_name=None,
        preprocessor_version=None,
        model_name=None,
        model_parameters=None,
        primary_metric="macro_f1",
        output_directory=str(output_dir),
    )
    write_json(output_dir / "manifest.json", manifest.model_dump(mode="json"))
    return output_dir
