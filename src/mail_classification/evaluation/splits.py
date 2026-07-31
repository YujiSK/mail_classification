"""Common, group-aware 5-fold CV split shared by every Core condition/model."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

from mail_classification.generation.io import write_json
from mail_classification.schemas import (
    FoldArtifact,
    FoldMetadata,
    FoldRecord,
    FoldRole,
    RawMailRecord,
    sha256_file,
)


def audit_template_groups(records: list[RawMailRecord]) -> dict[str, object]:
    """Describe how ``template_group`` relates to ``label`` and sample counts.

    ``task10_architecture.md`` requires this audit to decide, on real data,
    whether ``StratifiedGroupKFold`` (group structure real) or plain
    ``StratifiedKFold`` (no real grouping) is the correct splitter.
    """
    if not records:
        raise ValueError("template-group audit requires at least one record")

    group_sizes: Counter[str] = Counter()
    group_labels: dict[str, set[str]] = defaultdict(set)
    groups_per_label: dict[str, set[str]] = defaultdict(set)
    for record in records:
        group_sizes[record.template_group] += 1
        group_labels[record.template_group].add(record.label.value)
        groups_per_label[record.label.value].add(record.template_group)

    groups_spanning_multiple_labels = {
        group: sorted(labels)
        for group, labels in group_labels.items()
        if len(labels) > 1
    }
    has_group_structure = 0 < len(group_sizes) < len(records)

    return {
        "sample_count": len(records),
        "unique_group_count": len(group_sizes),
        "group_sizes": dict(sorted(group_sizes.items())),
        "groups_per_label": {
            label: len(groups) for label, groups in sorted(groups_per_label.items())
        },
        "groups_spanning_multiple_labels": groups_spanning_multiple_labels,
        "has_group_structure": has_group_structure,
    }


def recommend_splitter_name(audit: dict[str, object]) -> str:
    """Pick the splitter per the architecture contract's stated rule.

    Group structure is used only when it is real (more than one sample per
    group on average) and clean (no group mixes more than one label, which
    would make group-preserving stratification ambiguous).
    """
    if audit["has_group_structure"] and not audit["groups_spanning_multiple_labels"]:
        return "StratifiedGroupKFold"
    return "StratifiedKFold"


def build_common_folds(
    records: list[RawMailRecord],
    data_hash: str,
    *,
    n_splits: int = 5,
    random_seed: int = 42,
) -> FoldArtifact:
    """Generate the one shared Fold assignment reused by every condition/model.

    Every sample is assigned exactly one validation fold; ``FoldArtifact``'s
    own cross-record validation then guarantees no sample or template_group
    is split between train and validation within the same fold.
    """
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")

    audit = audit_template_groups(records)
    splitter_name = recommend_splitter_name(audit)
    labels = [record.label.value for record in records]

    if splitter_name == "StratifiedGroupKFold":
        splitter = StratifiedGroupKFold(
            n_splits=n_splits, shuffle=True, random_state=random_seed
        )
        groups = [record.template_group for record in records]
        splits = splitter.split(range(len(records)), labels, groups)
    else:
        splitter = StratifiedKFold(
            n_splits=n_splits, shuffle=True, random_state=random_seed
        )
        splits = splitter.split(range(len(records)), labels)

    validation_fold_by_index: dict[int, int] = {}
    for fold_id, (_train_idx, validation_idx) in enumerate(splits):
        for index in validation_idx:
            validation_fold_by_index[index] = fold_id

    fold_records = [
        FoldRecord(
            sample_id=record.id,
            fold_id=fold_id,
            split_role=(
                FoldRole.VALIDATION
                if fold_id == validation_fold_by_index[index]
                else FoldRole.TRAIN
            ),
            label=record.label,
            template_group=record.template_group,
        )
        for index, record in enumerate(records)
        for fold_id in range(n_splits)
    ]

    metadata = FoldMetadata(
        created_at=datetime.now(timezone.utc),
        splitter_name=splitter_name,
        n_splits=n_splits,
        random_seed=random_seed,
        data_hash=data_hash,
    )
    return FoldArtifact(metadata=metadata, records=fold_records)


def write_fold_artifact(path: str | Path, artifact: FoldArtifact) -> str:
    """Persist the shared Fold artifact as one canonical JSON file; return its hash."""
    write_json(path, artifact.model_dump(mode="json"))
    return sha256_file(path)
