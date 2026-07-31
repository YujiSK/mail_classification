from datetime import datetime, timezone

from mail_classification.explain import build_misclassification_rows, summarize_error_categories
from mail_classification.schemas import Difficulty, MailLabel, RawMailRecord


def _record(record_id, label, *, difficulty=Difficulty.EASY, has_header=False,
            has_signature=False, has_quoted_reply=False, multi_intent=False,
            secondary_intent=None, contains_negation=False) -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text="body",
        body_text="body",
        label=label,
        template_group=f"{label.value}-g0",
        difficulty=difficulty,
        has_header=has_header,
        has_signature=has_signature,
        has_quoted_reply=has_quoted_reply,
        generation_seed=1,
        template_id=f"{label.value}-g0",
        variation_id=0,
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        metadata={
            "multi_intent": multi_intent,
            "secondary_intent": secondary_intent,
            "contains_negation": contains_negation,
        },
    )


def _oof_row(sample_id, condition, model, fold_id, true_label, predicted_label):
    return {
        "sample_id": sample_id,
        "condition": condition,
        "model": model,
        "fold_id": fold_id,
        "true_label": true_label,
        "predicted_label": predicted_label,
    }


def test_build_misclassification_rows_skips_correct_predictions() -> None:
    record = _record("m1", MailLabel.BILLING)
    oof_rows = [_oof_row("m1", "D0", "linear_svc", 0, "billing", "billing")]

    rows = build_misclassification_rows(oof_rows, {"m1": record})

    assert rows == []


def test_build_misclassification_rows_categorizes_multi_intent_first() -> None:
    record = _record(
        "m1",
        MailLabel.BILLING,
        difficulty=Difficulty.HARD,
        multi_intent=True,
        secondary_intent="technical_issue",
    )
    oof_rows = [_oof_row("m1", "D0", "linear_svc", 0, "billing", "technical_issue")]

    rows = build_misclassification_rows(oof_rows, {"m1": record})

    assert len(rows) == 1
    assert rows[0]["primary_category"] == "multi_intent"
    assert rows[0]["secondary_intent"] == "technical_issue"
    assert rows[0]["multi_intent"] is True


def test_build_misclassification_rows_categorizes_ambiguous_difficulty() -> None:
    record = _record("m1", MailLabel.BILLING, difficulty=Difficulty.AMBIGUOUS)
    oof_rows = [_oof_row("m1", "D0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows(oof_rows, {"m1": record})

    assert rows[0]["primary_category"] == "ambiguous_difficulty"


def test_build_misclassification_rows_categorizes_structural_content() -> None:
    record = _record("m1", MailLabel.BILLING, has_signature=True)
    oof_rows = [_oof_row("m1", "D0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows(oof_rows, {"m1": record})

    assert rows[0]["primary_category"] == "structural_content"


def test_build_misclassification_rows_categorizes_negation_present() -> None:
    record = _record("m1", MailLabel.BILLING, contains_negation=True)
    oof_rows = [_oof_row("m1", "D0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows(oof_rows, {"m1": record})

    assert rows[0]["primary_category"] == "negation_present"


def test_build_misclassification_rows_falls_back_to_uncategorized() -> None:
    record = _record("m1", MailLabel.BILLING)
    oof_rows = [_oof_row("m1", "D0", "linear_svc", 0, "billing", "account_support")]

    rows = build_misclassification_rows(oof_rows, {"m1": record})

    assert rows[0]["primary_category"] == "uncategorized"


def test_summarize_error_categories_counts_per_condition_model_category() -> None:
    rows = [
        {"condition": "D0", "model": "linear_svc", "primary_category": "multi_intent"},
        {"condition": "D0", "model": "linear_svc", "primary_category": "multi_intent"},
        {"condition": "D0", "model": "linear_svc", "primary_category": "uncategorized"},
        {"condition": "D1", "model": "linear_svc", "primary_category": "multi_intent"},
    ]

    summary = summarize_error_categories(rows)

    counts = {
        (row["condition"], row["model"], row["primary_category"]): row["count"]
        for row in summary
    }
    assert counts[("D0", "linear_svc", "multi_intent")] == 2
    assert counts[("D0", "linear_svc", "uncategorized")] == 1
    assert counts[("D1", "linear_svc", "multi_intent")] == 1
