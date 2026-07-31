from test_cv import synthetic_fold_artifact, synthetic_records

from mail_classification.explain import (
    audit_top_features_for_structural_artifacts,
    extract_descriptive_full_fit_coefficients,
    extract_fold_coefficients,
)


def test_extract_fold_coefficients_covers_every_fold_and_label() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    rows = extract_fold_coefficients(records, artifact, "D0", "linear_svc", top_n=5)

    fold_ids = {row["fold_id"] for row in rows}
    assert fold_ids == set(range(5))
    labels = {row["label"] for row in rows}
    assert labels == {record.label.value for record in records}
    rank_types = {row["rank_type"] for row in rows}
    assert rank_types == {"top_positive", "top_negative", "top_absolute"}


def test_extract_fold_coefficients_respects_top_n() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    rows = extract_fold_coefficients(records, artifact, "D0", "linear_svc", top_n=3)

    counts = {}
    for row in rows:
        key = (row["fold_id"], row["label"], row["rank_type"])
        counts[key] = counts.get(key, 0) + 1
    assert all(count <= 3 for count in counts.values())


def test_extract_fold_coefficients_ranks_are_consistent_with_sign() -> None:
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)

    rows = extract_fold_coefficients(records, artifact, "D0", "linear_svc", top_n=5)

    positive = [row for row in rows if row["rank_type"] == "top_positive"]
    negative = [row for row in rows if row["rank_type"] == "top_negative"]
    # top_positive rank 1 must have the largest coefficient for that (fold, label)
    for row in positive:
        if row["rank"] == 1:
            same_group = [
                r
                for r in positive
                if r["fold_id"] == row["fold_id"] and r["label"] == row["label"]
            ]
            assert row["coefficient"] == max(r["coefficient"] for r in same_group)
    for row in negative:
        if row["rank"] == 1:
            same_group = [
                r
                for r in negative
                if r["fold_id"] == row["fold_id"] and r["label"] == row["label"]
            ]
            assert row["coefficient"] == min(r["coefficient"] for r in same_group)


def test_extract_descriptive_full_fit_coefficients_has_no_fold_id_field() -> None:
    records = synthetic_records()

    rows = extract_descriptive_full_fit_coefficients(records, "D0", "linear_svc", top_n=3)

    assert rows
    assert all("fold_id" not in row for row in rows)
    assert all(row["condition"] == "D0" and row["model"] == "linear_svc" for row in rows)


def test_audit_top_features_for_structural_artifacts_flags_known_tokens() -> None:
    rows = [
        {"feature": "subject", "coefficient": 1.0},
        {"feature": "invoice", "coefficient": 0.5},
        {"feature": "URL", "coefficient": 0.3},
    ]

    flagged = audit_top_features_for_structural_artifacts(rows)

    assert {row["feature"] for row in flagged} == {"subject", "URL"}


def test_audit_top_features_for_structural_artifacts_empty_when_none_match() -> None:
    rows = [{"feature": "invoice", "coefficient": 0.5}]

    assert audit_top_features_for_structural_artifacts(rows) == []
