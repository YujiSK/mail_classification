from datetime import datetime, timezone
import json

import pytest
from pydantic import ValidationError

from mail_classification.schemas import (
    FoldArtifact,
    FoldMetadata,
    FoldRecord,
    RawMailRecord,
    RunManifest,
    sha256_bytes,
)

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
HASH = "a" * 64


def raw_record_data() -> dict[str, object]:
    return {
        "id": "mail-001",
        "raw_text": "Subject: Help\nI cannot log in.",
        "body_text": "I cannot log in.",
        "label": "account_support",
        "template_group": "account-login",
        "difficulty": "medium",
        "has_header": True,
        "has_signature": False,
        "has_quoted_reply": False,
        "generation_seed": 42,
        "template_id": "account-01",
        "variation_id": 0,
        "generated_at": NOW,
        "metadata": {"generator": "future", "score": 1},
    }


def manifest_data() -> dict[str, object]:
    return {
        "run_id": "run-001",
        "created_at": NOW,
        "git_commit": None,
        "git_dirty": None,
        "command": None,
        "python_version": None,
        "platform": None,
        "dependency_versions": {"pydantic": "2.13.4"},
        "config_path": "configs/phase1.yml",
        "config_hash": HASH,
        "data_path": None,
        "data_hash": None,
        "data_generation_seed": 42,
        "cv_seed": 42,
        "fold_artifact_path": None,
        "fold_artifact_hash": None,
        "preprocessor_name": "english_minimal",
        "preprocessor_version": "1.0.0",
        "model_name": None,
        "model_parameters": None,
        "primary_metric": "macro_f1",
        "output_directory": "outputs/runs/run-001",
    }


def fold_metadata() -> FoldMetadata:
    return FoldMetadata(
        created_at=NOW,
        splitter_name="StratifiedGroupKFold",
        n_splits=2,
        random_seed=42,
        data_hash=HASH,
    )


def test_raw_record_json_round_trip_preserves_raw_text() -> None:
    record = RawMailRecord(**raw_record_data())
    restored = RawMailRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.raw_text == raw_record_data()["raw_text"]


@pytest.mark.parametrize(
    "label",
    ["product_inquiry", "technical_issue", "billing", "account_support"],
)
def test_raw_record_accepts_each_supported_label(label: str) -> None:
    data = raw_record_data()
    data["label"] = label
    assert RawMailRecord(**data).label.value == label


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard", "ambiguous"])
def test_raw_record_accepts_each_supported_difficulty(difficulty: str) -> None:
    data = raw_record_data()
    data["difficulty"] = difficulty
    assert RawMailRecord(**data).difficulty.value == difficulty


def test_raw_record_requires_raw_text() -> None:
    data = raw_record_data()
    del data["raw_text"]
    with pytest.raises(ValidationError):
        RawMailRecord(**data)


@pytest.mark.parametrize("field", ["id", "raw_text", "body_text", "template_group"])
def test_raw_record_rejects_blank_required_text(field: str) -> None:
    data = raw_record_data()
    data[field] = " \n"
    with pytest.raises(ValidationError):
        RawMailRecord(**data)


def test_raw_record_rejects_unknown_label_and_difficulty() -> None:
    data = raw_record_data()
    data["label"] = "unknown"
    data["difficulty"] = "impossible"
    with pytest.raises(ValidationError) as error:
        RawMailRecord(**data)
    assert error.value.error_count() == 2


def test_raw_record_rejects_naive_datetime() -> None:
    data = raw_record_data()
    data["generated_at"] = datetime(2026, 7, 31)
    with pytest.raises(ValidationError, match="UTC offset"):
        RawMailRecord(**data)


def test_raw_record_rejects_non_json_metadata() -> None:
    data = raw_record_data()
    data["metadata"] = {"bad": {1, 2}}
    with pytest.raises(ValidationError, match="JSON-compatible"):
        RawMailRecord(**data)


def test_manifest_round_trip_and_null_acquisition_fields() -> None:
    manifest = RunManifest(**manifest_data())
    restored = RunManifest.model_validate_json(manifest.model_dump_json())
    assert restored == manifest
    assert restored.git_commit is None
    assert restored.python_version is None
    assert restored.dependency_versions == {"pydantic": "2.13.4"}


def test_manifest_rejects_naive_created_at() -> None:
    data = manifest_data()
    data["created_at"] = datetime(2026, 7, 31)
    with pytest.raises(ValidationError, match="UTC offset"):
        RunManifest(**data)


def test_manifest_rejects_invalid_hash() -> None:
    data = manifest_data()
    data["config_hash"] = "not-a-sha256"
    with pytest.raises(ValidationError):
        RunManifest(**data)


def test_manifest_paths_need_not_exist() -> None:
    data = manifest_data()
    data["data_path"] = "/does/not/exist.jsonl"
    data["data_hash"] = HASH
    assert RunManifest(**data).data_path == "/does/not/exist.jsonl"


def test_sha256_convention_hashes_exact_bytes() -> None:
    assert sha256_bytes(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )
    assert sha256_bytes(b"abc\n") != sha256_bytes(b"abc")


def test_fold_artifact_json_round_trip() -> None:
    artifact = FoldArtifact(
        metadata=fold_metadata(),
        records=[
            FoldRecord(
                sample_id="a",
                fold_id=0,
                split_role="train",
                label="billing",
                template_group="g-train",
            ),
            FoldRecord(
                sample_id="b",
                fold_id=0,
                split_role="validation",
                label="technical_issue",
                template_group="g-validation",
            ),
        ],
    )
    assert FoldArtifact.model_validate_json(artifact.model_dump_json()) == artifact


def test_fold_rejects_sample_overlap_within_fold() -> None:
    records = [
        FoldRecord(
            sample_id="a",
            fold_id=0,
            split_role=role,
            label="billing",
            template_group=f"g-{role}",
        )
        for role in ("train", "validation")
    ]
    with pytest.raises(ValidationError, match="sample may appear only once"):
        FoldArtifact(metadata=fold_metadata(), records=records)


def test_fold_rejects_group_mixing_within_fold() -> None:
    records = [
        FoldRecord(
            sample_id=sample,
            fold_id=0,
            split_role=role,
            label="billing",
            template_group="same-group",
        )
        for sample, role in (("a", "train"), ("b", "validation"))
    ]
    with pytest.raises(ValidationError, match="template_group"):
        FoldArtifact(metadata=fold_metadata(), records=records)


def test_fold_rejects_out_of_range_fold_id() -> None:
    record = FoldRecord(
        sample_id="a",
        fold_id=2,
        split_role="train",
        label="billing",
        template_group="g",
    )
    with pytest.raises(ValidationError, match="n_splits"):
        FoldArtifact(metadata=fold_metadata(), records=[record])


def test_fold_rejects_invalid_split_role() -> None:
    with pytest.raises(ValidationError):
        FoldRecord(
            sample_id="a",
            fold_id=0,
            split_role="test",
            label="billing",
            template_group="g",
        )


def test_fold_rejects_negative_fold_id() -> None:
    with pytest.raises(ValidationError):
        FoldRecord(
            sample_id="a",
            fold_id=-1,
            split_role="train",
            label="billing",
            template_group="g",
        )


def test_models_reject_extra_fields() -> None:
    data = manifest_data()
    data["silent_typo"] = True
    with pytest.raises(ValidationError):
        RunManifest(**data)


def test_schema_output_is_standard_json() -> None:
    payload = RawMailRecord(**raw_record_data()).model_dump_json()
    assert json.loads(payload)["generated_at"].endswith("Z")
