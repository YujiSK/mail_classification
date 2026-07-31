from pathlib import Path

import pytest
from sklearn.exceptions import NotFittedError
from sklearn.pipeline import Pipeline

from mail_classification.evaluation import (
    build_common_folds,
    load_verified_full_dataset,
    verify_full_dataset_hash,
)
from mail_classification.models import CORE_CLASSIFIERS, build_core_pipeline
from mail_classification.schemas import FoldRole

ROOT = Path(__file__).parents[1]

TRAIN_TEXTS = [
    "I would like to know the price of your product.",
    "The app keeps crashing when I try to log in.",
    "Please explain this extra charge on my invoice.",
    "I cannot reset my account password.",
    "Do you have this item in a different color?",
    "The website returns an error every time I upload a file.",
    "Why was I billed twice this month?",
    "My account was locked after too many login attempts.",
]
TRAIN_LABELS = [
    "product_inquiry",
    "technical_issue",
    "billing",
    "account_support",
    "product_inquiry",
    "technical_issue",
    "billing",
    "account_support",
]


def test_build_core_pipeline_rejects_unknown_model_name() -> None:
    with pytest.raises(ValueError, match="unknown Core model_name"):
        build_core_pipeline("random_forest")


@pytest.mark.parametrize("model_name", sorted(CORE_CLASSIFIERS))
def test_build_core_pipeline_has_tfidf_and_expected_classifier(
    model_name: str,
) -> None:
    pipeline = build_core_pipeline(model_name)

    assert isinstance(pipeline, Pipeline)
    assert [name for name, _ in pipeline.steps] == ["tfidf", "clf"]
    assert isinstance(pipeline.named_steps["clf"], CORE_CLASSIFIERS[model_name])


@pytest.mark.parametrize("model_name", sorted(CORE_CLASSIFIERS))
def test_build_core_pipeline_smoke_fits_and_predicts(model_name: str) -> None:
    pipeline = build_core_pipeline(model_name)

    pipeline.fit(TRAIN_TEXTS, TRAIN_LABELS)
    predictions = pipeline.predict(TRAIN_TEXTS)

    assert len(predictions) == len(TRAIN_TEXTS)
    assert set(predictions) <= set(TRAIN_LABELS)


def test_build_core_pipeline_passes_through_tfidf_and_model_params() -> None:
    pipeline = build_core_pipeline(
        "logistic_regression",
        tfidf_params={"ngram_range": (1, 2), "lowercase": False},
        model_params={"C": 0.5, "max_iter": 500},
    )

    vectorizer = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["clf"]
    assert vectorizer.ngram_range == (1, 2)
    assert vectorizer.lowercase is False
    assert classifier.C == 0.5
    assert classifier.max_iter == 500


def test_build_core_pipeline_does_not_fit_tfidf_before_pipeline_fit() -> None:
    pipeline = build_core_pipeline("linear_svc")

    with pytest.raises(NotFittedError):
        pipeline.named_steps["tfidf"].transform(["anything"])


@pytest.mark.parametrize("model_name", sorted(CORE_CLASSIFIERS))
def test_core_pipeline_fits_on_one_real_fold_and_predicts_the_other(
    model_name: str,
) -> None:
    full_data_path = ROOT / "data" / "raw" / "full_emails.jsonl"
    decision_path = ROOT / "docs" / "reviews" / "full_review_decision.json"
    if not full_data_path.is_file():
        pytest.skip("data/raw/full_emails.jsonl is not generated locally")

    data_hash = verify_full_dataset_hash(full_data_path, decision_path)
    records = load_verified_full_dataset(full_data_path, decision_path)
    artifact = build_common_folds(records, data_hash=data_hash)

    records_by_id = {record.id: record for record in records}
    fold_zero = [row for row in artifact.records if row.fold_id == 0]
    train_ids = [row.sample_id for row in fold_zero if row.split_role is FoldRole.TRAIN]
    validation_ids = [
        row.sample_id for row in fold_zero if row.split_role is FoldRole.VALIDATION
    ]

    pipeline = build_core_pipeline(model_name)
    pipeline.fit(
        [records_by_id[sample_id].raw_text for sample_id in train_ids],
        [records_by_id[sample_id].label.value for sample_id in train_ids],
    )
    predictions = pipeline.predict(
        [records_by_id[sample_id].raw_text for sample_id in validation_ids]
    )

    assert len(predictions) == len(validation_ids)
    known_labels = {records_by_id[sample_id].label.value for sample_id in train_ids}
    assert set(predictions) <= known_labels
