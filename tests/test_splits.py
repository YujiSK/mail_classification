from datetime import datetime, timezone
from pathlib import Path

import pytest

from mail_classification.evaluation import (
    audit_template_groups,
    build_common_folds,
    load_verified_full_dataset,
    recommend_splitter_name,
    write_fold_artifact,
)
from mail_classification.schemas import Difficulty, FoldRole, MailLabel, RawMailRecord

ROOT = Path(__file__).parents[1]
LABELS = [
    MailLabel.PRODUCT_INQUIRY,
    MailLabel.TECHNICAL_ISSUE,
    MailLabel.ACCOUNT_SUPPORT,
]
GROUPS_PER_LABEL = 5
SAMPLES_PER_GROUP = 4


def _record(record_id: str, label: MailLabel, template_group: str) -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text=f"body for {record_id}",
        body_text=f"body for {record_id}",
        label=label,
        template_group=template_group,
        difficulty=Difficulty.EASY,
        has_header=False,
        has_signature=False,
        has_quoted_reply=False,
        generation_seed=1,
        template_id=template_group,
        variation_id=0,
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )


def grouped_records() -> list[RawMailRecord]:
    records = []
    for label in LABELS:
        for group_index in range(GROUPS_PER_LABEL):
            group = f"{label.value}-g{group_index}"
            for sample_index in range(SAMPLES_PER_GROUP):
                records.append(
                    _record(f"{group}-s{sample_index}", label, group)
                )
    return records


def ungrouped_records() -> list[RawMailRecord]:
    return [
        _record(f"m{i}", LABELS[i % len(LABELS)], f"m{i}")
        for i in range(30)
    ]


def test_audit_template_groups_detects_clean_group_structure() -> None:
    audit = audit_template_groups(grouped_records())

    assert audit["sample_count"] == len(LABELS) * GROUPS_PER_LABEL * SAMPLES_PER_GROUP
    assert audit["unique_group_count"] == len(LABELS) * GROUPS_PER_LABEL
    assert audit["has_group_structure"] is True
    assert audit["groups_spanning_multiple_labels"] == {}
    assert audit["groups_per_label"] == {
        label.value: GROUPS_PER_LABEL for label in LABELS
    }
    assert set(audit["group_sizes"].values()) == {SAMPLES_PER_GROUP}


def test_audit_template_groups_detects_no_group_structure() -> None:
    audit = audit_template_groups(ungrouped_records())

    assert audit["has_group_structure"] is False


def test_audit_template_groups_flags_group_spanning_multiple_labels() -> None:
    records = grouped_records()
    contaminated = records[0].model_copy(update={"label": LABELS[1]})
    records[0] = contaminated

    audit = audit_template_groups(records)

    assert contaminated.template_group in audit["groups_spanning_multiple_labels"]


def test_audit_template_groups_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one record"):
        audit_template_groups([])


def test_recommend_splitter_name_prefers_group_aware_when_clean() -> None:
    audit = audit_template_groups(grouped_records())

    assert recommend_splitter_name(audit) == "StratifiedGroupKFold"


def test_recommend_splitter_name_falls_back_without_group_structure() -> None:
    audit = audit_template_groups(ungrouped_records())

    assert recommend_splitter_name(audit) == "StratifiedKFold"


def test_recommend_splitter_name_falls_back_when_groups_span_labels() -> None:
    records = grouped_records()
    records[0] = records[0].model_copy(update={"label": LABELS[1]})

    audit = audit_template_groups(records)

    assert recommend_splitter_name(audit) == "StratifiedKFold"


def test_build_common_folds_covers_every_sample_exactly_once_per_role() -> None:
    records = grouped_records()
    artifact = build_common_folds(records, data_hash="a" * 64, n_splits=5)

    assert artifact.metadata.splitter_name == "StratifiedGroupKFold"
    assert artifact.metadata.n_splits == 5
    assert artifact.metadata.data_hash == "a" * 64
    assert len(artifact.records) == len(records) * 5

    validation_folds: dict[str, set[int]] = {}
    for fold_record in artifact.records:
        if fold_record.split_role is FoldRole.VALIDATION:
            validation_folds.setdefault(fold_record.sample_id, set()).add(
                fold_record.fold_id
            )
    assert set(validation_folds) == {record.id for record in records}
    assert all(len(folds) == 1 for folds in validation_folds.values())


def test_build_common_folds_never_splits_a_group_within_one_fold() -> None:
    records = grouped_records()
    artifact = build_common_folds(records, data_hash="a" * 64, n_splits=5)

    roles_by_fold_and_group: dict[tuple[int, str], set[FoldRole]] = {}
    for fold_record in artifact.records:
        key = (fold_record.fold_id, fold_record.template_group)
        roles_by_fold_and_group.setdefault(key, set()).add(fold_record.split_role)

    assert all(len(roles) == 1 for roles in roles_by_fold_and_group.values())


def test_build_common_folds_is_reproducible_for_the_same_seed() -> None:
    records = grouped_records()
    first = build_common_folds(records, data_hash="a" * 64, random_seed=42)
    second = build_common_folds(records, data_hash="a" * 64, random_seed=42)

    def assignment(artifact):
        return {
            (r.sample_id, r.fold_id): r.split_role for r in artifact.records
        }

    assert assignment(first) == assignment(second)


def test_build_common_folds_falls_back_to_stratified_kfold_without_groups() -> None:
    records = ungrouped_records()
    artifact = build_common_folds(records, data_hash="a" * 64, n_splits=5)

    assert artifact.metadata.splitter_name == "StratifiedKFold"
    assert len(artifact.records) == len(records) * 5


def test_build_common_folds_rejects_n_splits_below_two() -> None:
    with pytest.raises(ValueError, match="n_splits"):
        build_common_folds(grouped_records(), data_hash="a" * 64, n_splits=1)


def test_write_fold_artifact_round_trips_through_json(tmp_path: Path) -> None:
    records = grouped_records()
    artifact = build_common_folds(records, data_hash="a" * 64)
    path = tmp_path / "common_folds.json"

    returned_hash = write_fold_artifact(path, artifact)

    from mail_classification.schemas import sha256_file

    assert returned_hash == sha256_file(path)
    assert path.is_file()


def test_common_folds_on_real_full_dataset_use_group_aware_split() -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    if not full_data_path.is_file():
        pytest.skip("data/raw/full_emails.jsonl is not generated locally")

    records = load_verified_full_dataset(full_data_path, decision_path)
    audit = audit_template_groups(records)
    assert audit["unique_group_count"] == 24
    assert audit["groups_spanning_multiple_labels"] == {}
    assert recommend_splitter_name(audit) == "StratifiedGroupKFold"

    artifact = build_common_folds(
        records,
        data_hash="53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc",
    )
    assert len(artifact.records) == len(records) * 5

    roles_by_fold_and_group: dict[tuple[int, str], set[FoldRole]] = {}
    for fold_record in artifact.records:
        key = (fold_record.fold_id, fold_record.template_group)
        roles_by_fold_and_group.setdefault(key, set()).add(fold_record.split_role)
    assert all(len(roles) == 1 for roles in roles_by_fold_and_group.values())
