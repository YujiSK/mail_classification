from test_cv import synthetic_fold_artifact, synthetic_records

from mail_classification.explain import enrich_misclassifications_with_evidence
from mail_classification.schemas import FoldRole, MailLabel


def _fixture():
    records = synthetic_records()
    artifact = synthetic_fold_artifact(records)
    return records, artifact


def _fabricated_misclassification(artifact, records, fold_id: int) -> dict:
    """A deterministic (sample_id, true_label, predicted_label) pair from real fold data.

    ``enrich_misclassifications_with_evidence`` only needs a valid sample_id and a
    predicted_label that is one of the model's classes; it does not re-derive
    predicted_label from the model, so this does not depend on the model actually
    making this particular mistake (the real Phase 4 run may or may not produce
    misclassifications on any given synthetic fixture/seed).
    """
    validation_row = next(
        row
        for row in artifact.records
        if row.fold_id == fold_id and row.split_role is FoldRole.VALIDATION
    )
    record = next(r for r in records if r.id == validation_row.sample_id)
    true_label = record.label.value
    predicted_label = next(
        label.value for label in MailLabel if label.value != true_label
    )
    return {
        "sample_id": record.id,
        "condition": "D0",
        "model": "linear_svc",
        "fold_id": fold_id,
        "true_label": true_label,
        "predicted_label": predicted_label,
    }


def test_enrich_misclassifications_returns_empty_for_no_errors() -> None:
    records, artifact = _fixture()

    assert enrich_misclassifications_with_evidence([], records, artifact) == []


def test_enrich_misclassifications_adds_decision_scores_for_every_label() -> None:
    records, artifact = _fixture()
    misclassifications = [_fabricated_misclassification(artifact, records, 0)]

    enriched = enrich_misclassifications_with_evidence(misclassifications, records, artifact)

    assert len(enriched) == 1
    for label in MailLabel:
        key = f"decision_score_{label.value}"
        assert key in enriched[0]
        assert isinstance(enriched[0][key], float)


def test_enrich_misclassifications_never_changes_true_or_predicted_label() -> None:
    records, artifact = _fixture()
    original = _fabricated_misclassification(artifact, records, 1)

    enriched = enrich_misclassifications_with_evidence([original], records, artifact)

    assert enriched[0]["true_label"] == original["true_label"]
    assert enriched[0]["predicted_label"] == original["predicted_label"]
    assert enriched[0]["sample_id"] == original["sample_id"]


def test_enrich_misclassifications_top_features_are_nonempty_strings() -> None:
    records, artifact = _fixture()
    misclassifications = [_fabricated_misclassification(artifact, records, 2)]

    enriched = enrich_misclassifications_with_evidence(misclassifications, records, artifact)

    assert isinstance(enriched[0]["predicted_top_features"], str)
    assert isinstance(enriched[0]["true_top_features"], str)
    assert enriched[0]["predicted_top_features"] != ""
    assert enriched[0]["true_top_features"] != ""


def test_enrich_misclassifications_handles_multiple_cells_and_folds() -> None:
    records, artifact = _fixture()
    rows = [
        _fabricated_misclassification(artifact, records, 0),
        {**_fabricated_misclassification(artifact, records, 1), "model": "logistic_regression"},
        _fabricated_misclassification(artifact, records, 3),
    ]

    enriched = enrich_misclassifications_with_evidence(rows, records, artifact)

    assert len(enriched) == 3
    assert {(row["fold_id"], row["model"]) for row in enriched} == {
        (0, "linear_svc"),
        (1, "logistic_regression"),
        (3, "linear_svc"),
    }
