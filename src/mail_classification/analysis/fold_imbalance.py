"""Quantify validation-fold imbalance from existing immutable artifacts only.

This module never creates Fold assignments and never trains a model. It joins
the canonical common-Fold artifact to the Full JSONL by sample ID, validates
their label/template-group agreement, and writes a deterministic CSV.
"""

from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path

import pandas as pd

from mail_classification.generation.io import read_jsonl
from mail_classification.schemas import FoldArtifact

FOLD_IMBALANCE_FIELDS = [
    "data_hash",
    "fold_artifact_hash",
    "fold_id",
    "label",
    "n_template_groups",
    "n_samples",
    "template_group_breakdown",
]
_ALL_LABEL = "ALL"


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validated_join(
    fold_artifact_path: str | Path, full_data_path: str | Path
) -> tuple[FoldArtifact, pd.DataFrame, str]:
    fold_path = Path(fold_artifact_path)
    full_path = Path(full_data_path)
    artifact = FoldArtifact.model_validate_json(fold_path.read_text(encoding="utf-8"))
    full_records = read_jsonl(full_path)

    actual_data_hash = _sha256(full_path)
    if actual_data_hash != artifact.metadata.data_hash:
        raise ValueError(
            "Full dataset SHA-256 does not match the common Fold artifact: "
            f"actual={actual_data_hash}, expected={artifact.metadata.data_hash}"
        )

    full_by_id = {record.id: record for record in full_records}
    if len(full_by_id) != len(full_records):
        raise ValueError("Full dataset contains duplicate sample IDs")

    validation_records = [
        record for record in artifact.records if record.split_role.value == "validation"
    ]
    validation_ids = [record.sample_id for record in validation_records]
    if len(validation_ids) != len(set(validation_ids)):
        raise ValueError("a sample_id has more than one validation-fold assignment")

    expected_ids = set(full_by_id)
    actual_ids = set(validation_ids)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        unknown = sorted(actual_ids - expected_ids)
        raise ValueError(
            "validation assignment and Full dataset must have exact sample coverage: "
            f"missing={missing[:5]}, unknown={unknown[:5]}"
        )

    joined_rows: list[dict[str, object]] = []
    for assignment in validation_records:
        source = full_by_id[assignment.sample_id]
        source_label = source.label.value
        if assignment.label.value != source_label:
            raise ValueError(
                f"label mismatch for {assignment.sample_id}: "
                f"Fold={assignment.label.value!r}, Full={source_label!r}"
            )
        if assignment.template_group != source.template_group:
            raise ValueError(
                f"template_group mismatch for {assignment.sample_id}: "
                f"Fold={assignment.template_group!r}, Full={source.template_group!r}"
            )
        joined_rows.append(
            {
                "sample_id": assignment.sample_id,
                "fold_id": assignment.fold_id,
                "label": source_label,
                "template_group": source.template_group,
            }
        )

    observed_folds = {int(row["fold_id"]) for row in joined_rows}
    expected_folds = set(range(artifact.metadata.n_splits))
    if observed_folds != expected_folds:
        raise ValueError(
            f"validation fold IDs must be {sorted(expected_folds)}, got {sorted(observed_folds)}"
        )

    return artifact, pd.DataFrame(joined_rows), _sha256(fold_path)


def _breakdown(group_values: pd.Series) -> str:
    counts = Counter(str(value) for value in group_values)
    return ";".join(f"{group}:{counts[group]}" for group in sorted(counts))


def compute_fold_imbalance_stats(
    fold_artifact_path: str | Path, full_data_path: str | Path
) -> pd.DataFrame:
    """Return one row per fold/label plus one ``label=ALL`` total per fold.

    ``template_group_breakdown`` is a deterministic ``group:sample_count``
    list, making both the group identity and within-group count traceable.
    """
    artifact, joined, fold_artifact_hash = _validated_join(
        fold_artifact_path, full_data_path
    )
    rows: list[dict[str, object]] = []
    data_hash = artifact.metadata.data_hash

    for fold_id in range(artifact.metadata.n_splits):
        fold_rows = joined[joined["fold_id"] == fold_id]
        for label in sorted(str(value) for value in fold_rows["label"].unique()):
            label_rows = fold_rows[fold_rows["label"] == label]
            rows.append(
                {
                    "data_hash": data_hash,
                    "fold_artifact_hash": fold_artifact_hash,
                    "fold_id": fold_id,
                    "label": label,
                    "n_template_groups": int(label_rows["template_group"].nunique()),
                    "n_samples": int(len(label_rows)),
                    "template_group_breakdown": _breakdown(label_rows["template_group"]),
                }
            )
        rows.append(
            {
                "data_hash": data_hash,
                "fold_artifact_hash": fold_artifact_hash,
                "fold_id": fold_id,
                "label": _ALL_LABEL,
                "n_template_groups": int(fold_rows["template_group"].nunique()),
                "n_samples": int(len(fold_rows)),
                "template_group_breakdown": _breakdown(fold_rows["template_group"]),
            }
        )

    return pd.DataFrame(rows, columns=FOLD_IMBALANCE_FIELDS)


def write_fold_imbalance_stats(
    fold_artifact_path: str | Path, full_data_path: str | Path, output_path: str | Path
) -> Path:
    stats = compute_fold_imbalance_stats(fold_artifact_path, full_data_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(output, index=False, lineterminator="\n")
    return output
