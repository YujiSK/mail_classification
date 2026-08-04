from datetime import datetime, timezone
from pathlib import Path

from mail_classification.generation import (
    JapaneseSyntheticMailGenerator,
    load_generation_config,
    load_ja_template_catalog,
)
from mail_classification.generation.io import records_to_jsonl_bytes
from mail_classification.quality import build_full_spot_review_samples, build_review_samples
from mail_classification.quality.ja_duplicates import DUPLICATE_FIELDS, find_duplicates
from mail_classification.quality.ja_leakage import LEAKAGE_FIELDS, audit_leakage
from mail_classification.quality.ja_statistics import build_quality_statistics
from mail_classification.schemas import MailLabel, RawMailRecord, sha256_bytes

ROOT = Path(__file__).parents[1]
CONFIG = load_generation_config(ROOT / "configs" / "phase2_ja.yml")
CATALOG = load_ja_template_catalog(ROOT / CONFIG.paths.templates)
PILOT = JapaneseSyntheticMailGenerator(CONFIG, CATALOG).generate("pilot")
FULL = JapaneseSyntheticMailGenerator(CONFIG, CATALOG).generate("full")


def record(
    record_id: str,
    raw_text: str,
    body_text: str,
    label: str = "billing",
    group: str = "g1",
    **flags,
) -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text=raw_text,
        body_text=body_text,
        label=label,
        template_group=group,
        difficulty="easy",
        has_header=flags.get("has_header", False),
        has_signature=flags.get("has_signature", False),
        has_quoted_reply=flags.get("has_quoted_reply", False),
        generation_seed=1,
        template_id=f"t-{record_id}",
        variation_id=0,
        generated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        metadata={
            "multi_intent": False,
            "contains_negation": False,
            **flags.get("metadata", {}),
        },
    )


def test_exact_raw_and_body_duplicates_are_detected() -> None:
    records = [
        record("a", "同じメッセージ", "同じメッセージ", group="g1"),
        record("b", "同じメッセージ", "同じメッセージ", group="g2"),
    ]
    findings = find_duplicates(records)
    assert {item["source_field"] for item in findings if item["match_type"] == "exact"} == {
        "raw_text",
        "body_text",
    }


def test_normalized_duplicate_absorbs_header_signature_and_whitespace() -> None:
    records = [
        record(
            "a",
            "差出人: a@example.com\n件名: 確認\nログイン　できない\n\n--\nAlice",
            "ログイン　できない",
            group="g1",
            has_header=True,
            has_signature=True,
        ),
        record("b", "ログインできない", "ログインできない", group="g2"),
    ]
    findings = find_duplicates(records)
    assert any(
        item["match_type"] == "normalized" and item["source_field"] == "raw_text"
        for item in findings
    )


def test_distinct_messages_are_not_false_duplicates() -> None:
    assert find_duplicates(
        [
            record("a", "最初のご依頼です", "最初のご依頼です"),
            record("b", "別の内容のご依頼です", "別の内容のご依頼です"),
        ]
    ) == []


def test_duplicate_report_rows_have_stable_schema() -> None:
    findings = find_duplicates(
        [record("a", "同一", "同一"), record("b", "同一", "同一", group="g2")]
    )
    assert findings
    assert set(findings[0]) == set(DUPLICATE_FIELDS)


def test_pilot_has_no_exact_or_normalized_duplicates() -> None:
    assert find_duplicates(PILOT) == []


def test_pilot_has_no_error_or_warning_leakage_findings() -> None:
    findings = audit_leakage(PILOT, CONFIG.quality)
    assert not [
        finding
        for finding in findings
        if finding["severity"] in {"error", "warning"}
    ]


def test_full_has_no_duplicates_or_error_warning_leakage_findings() -> None:
    assert find_duplicates(FULL) == []
    thresholds = CONFIG.quality.model_copy(
        update={
            "exclusive_feature_min_count": (
                CONFIG.quality.full_exclusive_feature_min_count
            )
        }
    )
    findings = audit_leakage(FULL, thresholds)
    assert not [
        finding
        for finding in findings
        if finding["severity"] in {"error", "warning"}
    ]


def test_label_literal_leak_is_detected() -> None:
    finding = audit_leakage(
        [record("a", "product_inquiryへ転送してください", "product_inquiry")],
        CONFIG.quality,
    )
    assert any(item["category"] == "label_literal" for item in finding)


def test_class_specific_signature_and_header_are_detected() -> None:
    records = [
        record(
            f"b{i}",
            "差出人: person@only.example\n件名: 同じ件名\n本文\n\n--\n固有の会社名",
            f"本文 {i}",
            group=f"g{i}",
            has_header=True,
            has_signature=True,
        )
        for i in range(4)
    ]
    findings = audit_leakage(records, CONFIG.quality)
    categories = {item["category"] for item in findings}
    assert "class_specific_sender_domain" in categories
    assert "class_specific_signature" in categories


def test_length_difference_warning_is_detected() -> None:
    records = [
        record("a", "短い", "短い", label="billing", group="g1"),
        record(
            "b",
            "とても長い文章です。" * 100,
            "とても長い文章です。" * 100,
            label="technical_issue",
            group="g2",
        ),
    ]
    findings = audit_leakage(records, CONFIG.quality)
    assert any(item["category"] == "class_length_difference" for item in findings)


def test_leakage_report_rows_have_stable_schema() -> None:
    findings = audit_leakage(
        [record("a", "account_support", "account_support")], CONFIG.quality
    )
    assert findings
    assert all(set(item) == set(LEAKAGE_FIELDS) for item in findings)


def test_statistics_count_classes_difficulties_and_lengths() -> None:
    stats = build_quality_statistics(PILOT)
    assert stats["total_count"] == 96
    assert stats["class_counts"] == {label.value: 24 for label in MailLabel}
    assert set(stats["difficulty_counts"]) == {"easy", "medium", "hard"}
    assert stats["template_group_count"] == 24
    assert stats["variation_count"] == 96
    for label in MailLabel:
        assert stats["length_statistics"][label.value]["characters"]["min"] > 0
        assert stats["length_statistics"][label.value]["tokens"]["min"] > 0


def test_full_statistics_capture_required_distribution() -> None:
    stats = build_quality_statistics(FULL)
    assert stats["class_counts"] == {label.value: 200 for label in MailLabel}
    assert set(stats["template_group_counts"].values()) == {33, 34}
    assert set(stats["class_urgency_counts"].values()) == {50}


def test_output_hash_is_deterministic() -> None:
    payload = records_to_jsonl_bytes(PILOT)
    assert sha256_bytes(payload) == sha256_bytes(records_to_jsonl_bytes(PILOT))


def test_review_samples_cover_each_class_and_required_cases() -> None:
    leakage = audit_leakage(PILOT, CONFIG.quality)
    rows = build_review_samples(PILOT, 10, [], leakage)
    for label in MailLabel:
        assert sum(row["label"] == label.value for row in rows) >= 10
    reasons = "|".join(str(row["selection_reasons"]) for row in rows)
    for reason in (
        "difficulty:easy",
        "difficulty:medium",
        "difficulty:hard",
        "shortest",
        "longest",
        "negation",
        "multi_intent",
        "has_header",
        "has_signature",
        "has_quoted_reply",
    ):
        assert reason in reasons
    assert all(row["review_status"] == "" for row in rows)
    assert all(row["review_comment"] == "" for row in rows)


def test_full_spot_review_has_one_row_per_template_group() -> None:
    thresholds = CONFIG.quality.model_copy(
        update={
            "exclusive_feature_min_count": (
                CONFIG.quality.full_exclusive_feature_min_count
            )
        }
    )
    leakage = audit_leakage(FULL, thresholds)
    rows = build_full_spot_review_samples(FULL, leakage)
    assert len(rows) == 24
    assert len({row["template_group"] for row in rows}) == 24
    assert {row["label"] for row in rows} == {label.value for label in MailLabel}
    assert {row["difficulty"] for row in rows} == {"easy", "medium", "hard"}
