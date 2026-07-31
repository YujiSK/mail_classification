import pytest
from sklearn.pipeline import Pipeline

from mail_classification.models import (
    CORE_CONDITIONS,
    apply_condition_preprocessing,
    build_condition_pipeline,
)

SAMPLE_TEXT = (
    "From: sender@example.com\n"
    "Subject: Billing question\n\n"
    "Hi, please see http://example.com/invoice and contact reply@example.com.\n"
    "--\n"
    "Jane Doe\n"
    "\n"
    "> previous message\n"
    "On Mon, Jan 1, 2026, someone wrote:\n"
    "older thread content\n"
)


def test_exactly_three_approved_conditions() -> None:
    assert set(CORE_CONDITIONS) == {"D0", "D1", "D2"}


def test_d1_changes_only_tfidf_range_relative_to_d0() -> None:
    d0, d1 = CORE_CONDITIONS["D0"], CORE_CONDITIONS["D1"]

    assert d1.preprocessing_config == d0.preprocessing_config
    assert d1.tfidf_params != d0.tfidf_params
    assert d0.tfidf_params["ngram_range"] == (1, 1)
    assert d1.tfidf_params["ngram_range"] == (1, 2)


def test_d2_changes_only_cleaning_relative_to_d0() -> None:
    d0, d2 = CORE_CONDITIONS["D0"], CORE_CONDITIONS["D2"]

    assert d2.tfidf_params == d0.tfidf_params
    assert d2.preprocessing_config.normalization == d0.preprocessing_config.normalization
    assert d2.preprocessing_config.segmentation == d0.preprocessing_config.segmentation
    assert d2.preprocessing_config.cleaning != d0.preprocessing_config.cleaning

    d0_cleaning = d0.preprocessing_config.cleaning
    d2_cleaning = d2.preprocessing_config.cleaning
    for field in (
        "remove_headers",
        "remove_signatures",
        "remove_quoted_reply",
        "replace_urls",
        "replace_emails",
    ):
        assert getattr(d0_cleaning, field) is False
        assert getattr(d2_cleaning, field) is True
    # remove_html is intentionally constant across all conditions (basic
    # hygiene, not one of the approved ablation factors).
    assert d0_cleaning.remove_html == d2_cleaning.remove_html is True


def test_apply_condition_preprocessing_rejects_unknown_condition() -> None:
    with pytest.raises(ValueError, match="unknown Core condition"):
        apply_condition_preprocessing("D9", ["text"])


def test_d0_preprocessing_leaves_header_signature_quote_url_email_intact() -> None:
    (cleaned,) = apply_condition_preprocessing("D0", [SAMPLE_TEXT])

    assert "sender@example.com" in cleaned
    assert "http://example.com" in cleaned
    assert "jane doe" in cleaned
    assert "previous message" in cleaned


def test_d2_preprocessing_strips_header_signature_quote_and_masks_url_email() -> None:
    (cleaned,) = apply_condition_preprocessing("D2", [SAMPLE_TEXT])

    assert "sender@example.com" not in cleaned
    assert "reply@example.com" not in cleaned
    assert "http://example.com" not in cleaned
    assert "<url>" in cleaned
    assert "<email>" in cleaned
    assert "previous message" not in cleaned
    assert "jane doe" not in cleaned


def test_d1_preprocessing_matches_d0_preprocessing() -> None:
    d0_cleaned = apply_condition_preprocessing("D0", [SAMPLE_TEXT])
    d1_cleaned = apply_condition_preprocessing("D1", [SAMPLE_TEXT])

    assert d0_cleaned == d1_cleaned


@pytest.mark.parametrize("condition_name", sorted(CORE_CONDITIONS))
@pytest.mark.parametrize("model_name", ["linear_svc", "logistic_regression"])
def test_build_condition_pipeline_smoke_fits_for_every_cell(
    condition_name: str, model_name: str
) -> None:
    pipeline = build_condition_pipeline(condition_name, model_name)
    texts = apply_condition_preprocessing(
        condition_name,
        [
            "please help with my order",
            "the app will not open",
            "my invoice is wrong",
            "I am locked out of my account",
        ],
    )
    labels = ["product_inquiry", "technical_issue", "billing", "account_support"]

    assert isinstance(pipeline, Pipeline)
    pipeline.fit(texts, labels)
    predictions = pipeline.predict(texts)
    assert len(predictions) == len(texts)


def test_build_condition_pipeline_rejects_unknown_condition() -> None:
    with pytest.raises(ValueError, match="unknown Core condition"):
        build_condition_pipeline("D9", "linear_svc")


def test_build_condition_pipeline_rejects_unknown_model() -> None:
    with pytest.raises(ValueError, match="unknown Core model_name"):
        build_condition_pipeline("D0", "random_forest")
