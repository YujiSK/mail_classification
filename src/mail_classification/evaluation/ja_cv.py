"""Japanese counterpart of ``cv.py``.

Identical fit/predict logic; the only difference is importing the J0-JC
condition functions from ``models.conditions_ja`` instead of the English
D0-D2 functions from ``models`` (``cv.py`` imports those at module level, so
passing a "J0" string into the English module would just raise). Forked
rather than parameterized so ``cv.py`` and its hash-fixed English Phase 4
output stay untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from mail_classification.models import (
    apply_condition_preprocessing_ja,
    build_condition_pipeline_ja,
)
from mail_classification.schemas import FoldArtifact, FoldRole, RawMailRecord


@dataclass(frozen=True)
class FoldFitResult:
    condition: str
    model: str
    fold_id: int
    n_train: int
    n_test: int
    fit_seconds: float
    predict_seconds: float
    vocabulary_size: int
    oof_rows: tuple[dict[str, str], ...]  # sample_id, true_label, predicted_label


def run_core_cell(
    records: list[RawMailRecord],
    fold_artifact: FoldArtifact,
    condition_name: str,
    model_name: str,
) -> list[FoldFitResult]:
    """Fit/predict every fold of one (condition, model) cell; never refit on all data."""
    records_by_id = {record.id: record for record in records}
    preprocessed_by_id = dict(
        zip(
            (record.id for record in records),
            apply_condition_preprocessing_ja(
                condition_name, [record.raw_text for record in records]
            ),
        )
    )

    results: list[FoldFitResult] = []
    for fold_id in range(fold_artifact.metadata.n_splits):
        fold_rows = [row for row in fold_artifact.records if row.fold_id == fold_id]
        train_ids = [
            row.sample_id for row in fold_rows if row.split_role is FoldRole.TRAIN
        ]
        validation_ids = [
            row.sample_id for row in fold_rows if row.split_role is FoldRole.VALIDATION
        ]

        pipeline = build_condition_pipeline_ja(condition_name, model_name)
        x_train = [preprocessed_by_id[sample_id] for sample_id in train_ids]
        y_train = [records_by_id[sample_id].label.value for sample_id in train_ids]
        x_test = [preprocessed_by_id[sample_id] for sample_id in validation_ids]
        y_test = [records_by_id[sample_id].label.value for sample_id in validation_ids]

        start = time.perf_counter()
        pipeline.fit(x_train, y_train)
        fit_seconds = time.perf_counter() - start

        start = time.perf_counter()
        predictions = pipeline.predict(x_test)
        predict_seconds = time.perf_counter() - start

        oof_rows = tuple(
            {
                "sample_id": sample_id,
                "true_label": true_label,
                "predicted_label": predicted_label,
            }
            for sample_id, true_label, predicted_label in zip(
                validation_ids, y_test, predictions
            )
        )
        results.append(
            FoldFitResult(
                condition=condition_name,
                model=model_name,
                fold_id=fold_id,
                n_train=len(train_ids),
                n_test=len(validation_ids),
                fit_seconds=fit_seconds,
                predict_seconds=predict_seconds,
                vocabulary_size=len(pipeline.named_steps["tfidf"].vocabulary_),
                oof_rows=oof_rows,
            )
        )
    return results


def run_core_experiments(
    records: list[RawMailRecord],
    fold_artifact: FoldArtifact,
    *,
    conditions: tuple[str, ...] = ("J0", "J1", "J2", "JC"),
    models: tuple[str, ...] = ("linear_svc", "logistic_regression"),
) -> list[FoldFitResult]:
    """Fit/predict every (condition, model) cell on the same Fold artifact."""
    results: list[FoldFitResult] = []
    for condition_name in conditions:
        for model_name in models:
            results.extend(
                run_core_cell(records, fold_artifact, condition_name, model_name)
            )
    return results
