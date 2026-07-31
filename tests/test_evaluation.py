from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from mail_classification.evaluation import (
    approved_full_data_hash,
    load_verified_full_dataset,
    verify_full_dataset_hash,
)
from mail_classification.generation.io import write_jsonl
from mail_classification.schemas import Difficulty, MailLabel, RawMailRecord


def _record(record_id: str) -> RawMailRecord:
    return RawMailRecord(
        id=record_id,
        raw_text="Hello, I have a question about my order.",
        body_text="Hello, I have a question about my order.",
        label=MailLabel.PRODUCT_INQUIRY,
        template_group="tg001",
        difficulty=Difficulty.EASY,
        has_header=False,
        has_signature=False,
        has_quoted_reply=False,
        generation_seed=1,
        template_id="tg001",
        variation_id=0,
        generated_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )


def _write_decision(path: Path, *, full_data_hash: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"full_data_hash": full_data_hash}), encoding="utf-8")


def test_approved_full_data_hash_reads_tracked_decision(tmp_path: Path) -> None:
    decision_path = tmp_path / "docs" / "reviews" / "full_review_decision.json"
    _write_decision(decision_path, full_data_hash="a" * 64)

    assert approved_full_data_hash(decision_path) == "a" * 64


def test_approved_full_data_hash_missing_decision_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing"):
        approved_full_data_hash(tmp_path / "does_not_exist.json")


def test_approved_full_data_hash_missing_field(tmp_path: Path) -> None:
    decision_path = tmp_path / "full_review_decision.json"
    decision_path.write_text(json.dumps({"status": "approved"}), encoding="utf-8")

    with pytest.raises(ValueError, match="full_data_hash"):
        approved_full_data_hash(decision_path)


def test_verify_full_dataset_hash_accepts_matching_bytes(tmp_path: Path) -> None:
    data_path = tmp_path / "full_emails.jsonl"
    expected_hash = write_jsonl(data_path, [_record("m1"), _record("m2")])
    decision_path = tmp_path / "full_review_decision.json"
    _write_decision(decision_path, full_data_hash=expected_hash)

    assert verify_full_dataset_hash(data_path, decision_path) == expected_hash


def test_verify_full_dataset_hash_rejects_single_bit_difference(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "full_emails.jsonl"
    write_jsonl(data_path, [_record("m1"), _record("m2")])
    decision_path = tmp_path / "full_review_decision.json"
    _write_decision(decision_path, full_data_hash="0" * 64)

    with pytest.raises(ValueError, match="hash mismatch"):
        verify_full_dataset_hash(data_path, decision_path)


def test_verify_full_dataset_hash_missing_data_file(tmp_path: Path) -> None:
    decision_path = tmp_path / "full_review_decision.json"
    _write_decision(decision_path, full_data_hash="a" * 64)

    with pytest.raises(ValueError, match="missing"):
        verify_full_dataset_hash(tmp_path / "full_emails.jsonl", decision_path)


def test_load_verified_full_dataset_returns_records_on_match(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "full_emails.jsonl"
    records = [_record("m1"), _record("m2")]
    expected_hash = write_jsonl(data_path, records)
    decision_path = tmp_path / "full_review_decision.json"
    _write_decision(decision_path, full_data_hash=expected_hash)

    loaded = load_verified_full_dataset(data_path, decision_path)

    assert [record.id for record in loaded] == ["m1", "m2"]


def test_load_verified_full_dataset_fails_fast_on_single_bit_corruption(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "full_emails.jsonl"
    expected_hash = write_jsonl(data_path, [_record("m1")])
    decision_path = tmp_path / "full_review_decision.json"
    _write_decision(decision_path, full_data_hash=expected_hash)

    original = data_path.read_bytes()
    data_path.write_bytes(original[:-1] + bytes([original[-1] ^ 0x01]))

    with pytest.raises(ValueError, match="hash mismatch"):
        load_verified_full_dataset(data_path, decision_path)


def test_real_tracked_full_review_decision_matches_committed_hash_field() -> None:
    root = Path(__file__).parents[1]
    decision_path = root / "docs" / "reviews" / "full_review_decision.json"

    assert approved_full_data_hash(decision_path) == (
        "53c6f8949a2c3c2c75351122e31dff6b43ca6ff8a4d8326947d387b75b9a0bbc"
    )
