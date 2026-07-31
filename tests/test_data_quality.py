from datetime import datetime, timezone
from pathlib import Path

from mail_classification.generation import (
    SyntheticMailGenerator,
    load_generation_config,
    load_template_catalog,
)
from mail_classification.generation.io import records_to_jsonl_bytes
from mail_classification.quality import (
    audit_leakage,
    build_full_spot_review_samples,
    build_quality_statistics,
    build_review_samples,
    find_duplicates,
)
from mail_classification.quality.duplicates import DUPLICATE_FIELDS
from mail_classification.quality.leakage import LEAKAGE_FIELDS
from mail_classification.schemas import MailLabel, RawMailRecord, sha256_bytes

ROOT = Path(__file__).parents[1]
CONFIG = load_generation_config(ROOT / "configs" / "phase2.yml")
CATALOG = load_template_catalog(ROOT / CONFIG.paths.templates)
PILOT = SyntheticMailGenerator(CONFIG, CATALOG).generate("pilot")
FULL = SyntheticMailGenerator(CONFIG, CATALOG).generate("full")


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
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        metadata={
            "multi_intent": False,
            "contains_negation": False,
            **flags.get("metadata", {}),
        },
    )


def test_exact_raw_and_body_duplicates_are_detected() -> None:
    records = [
        record("a", "Same message", "Same message", group="g1"),
        record("b", "Same message", "Same message", group="g2"),
    ]
    findings = find_duplicates(records)
    assert {item["source_field"] for item in findings if item["match_type"] == "exact"} == {
        "raw_text",
        "body_text",
    }


def test_normalized_duplicate_absorbs_header_signature_case_and_whitespace() -> None:
    records = [
        record(
            "a",
            "From: a@example.com\nSubject: Help\nHELLO   WORLD\n\n--\nAlice",
            "HELLO   WORLD",
            group="g1",
            has_header=True,
            has_signature=True,
        ),
        record("b", "hello world", "hello world", group="g2"),
    ]
    findings = find_duplicates(records)
    assert any(
        item["match_type"] == "normalized" and item["source_field"] == "raw_text"
        for item in findings
    )


def test_distinct_messages_are_not_false_duplicates() -> None:
    assert find_duplicates(
        [
            record("a", "First request", "First request"),
            record("b", "Unrelated second request", "Unrelated second request"),
        ]
    ) == []


def test_duplicate_report_rows_have_stable_schema() -> None:
    findings = find_duplicates(
        [record("a", "same", "same"), record("b", "same", "same", group="g2")]
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
    assert len(findings) == 10


def test_label_literal_leak_is_detected() -> None:
    finding = audit_leakage(
        [record("a", "Please route product_inquiry now", "product_inquiry")],
        CONFIG.quality,
    )
    assert any(item["category"] == "label_literal" for item in finding)


def test_class_specific_signature_and_header_are_detected() -> None:
    records = [
        record(
            f"b{i}",
            "From: person@only.example\nSubject: Same\nText\n\n--\nUnique Company",
            f"Text {i}",
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
        record("a", "short", "short", label="billing", group="g1"),
        record(
            "b",
            "very long " * 100,
            "very long " * 100,
            label="technical_issue",
            group="g2",
        ),
    ]
    findings = audit_leakage(records, CONFIG.quality)
    assert any(item["category"] == "class_length_difference" for item in findings)


def test_template_concentration_warning_is_detected() -> None:
    records = [
        record(f"a{i}", f"message {i}", f"message {i}", group="one-group")
        for i in range(5)
    ]
    findings = audit_leakage(records, CONFIG.quality)
    assert any(item["category"] == "template_concentration" for item in findings)


def test_metadata_one_to_one_warning_is_detected() -> None:
    records = [
        record("a", "one", "one", label="billing", group="g1", has_header=True),
        record("b", "two", "two", label="technical_issue", group="g2"),
    ]
    findings = audit_leakage(records, CONFIG.quality)
    assert any(item["category"] == "metadata_one_to_one" for item in findings)


def test_shared_urgency_distribution_warning_is_detected() -> None:
    records = [
        record(
            f"b{i}",
            f"billing request {i}",
            f"billing request {i}",
            label="billing",
            group=f"bg{i}",
            metadata={"component_indices": {"urgency": 1}},
        )
        for i in range(4)
    ] + [
        record(
            f"t{i}",
            f"technical request {i}",
            f"technical request {i}",
            label="technical_issue",
            group=f"tg{i}",
            metadata={"component_indices": {"urgency": 0}},
        )
        for i in range(4)
    ]
    findings = audit_leakage(records, CONFIG.quality)
    assert any(
        item["category"] == "shared_component_distribution"
        for item in findings
    )


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
    reasons = "|".join(str(row["selection_reasons"]) for row in rows)
    assert "shortest" in reasons
    assert "longest" in reasons
    assert all(
        f"leakage_finding:{finding['feature']}" in reasons
        for finding in leakage
    )
    assert all(row["review_status"] == "" for row in rows)
