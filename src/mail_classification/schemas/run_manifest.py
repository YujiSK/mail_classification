"""Schema and hashing convention for a reproducible run manifest."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import JsonObject, Sha256Hex, require_aware_datetime, require_nonblank


def sha256_bytes(content: bytes) -> str:
    """Return lowercase SHA-256 for the exact supplied bytes."""
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash exact file bytes without newline or text-encoding conversion."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RunManifest(BaseModel):
    """Machine-readable provenance. Failed acquisition is represented by null."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: datetime
    git_commit: str | None
    git_dirty: bool | None
    command: list[str] | None
    python_version: str | None
    platform: str | None
    dependency_versions: dict[str, str] | None
    config_path: str | None
    config_hash: Sha256Hex | None
    data_path: str | None
    data_hash: Sha256Hex | None
    data_generation_seed: int | None = Field(ge=0)
    template_path: str | None = None
    template_hash: Sha256Hex | None = None
    generator_version: str | None = None
    approval_decision_path: str | None = None
    approval_decision_hash: Sha256Hex | None = None
    cv_seed: int | None = Field(ge=0)
    fold_artifact_path: str | None
    fold_artifact_hash: Sha256Hex | None
    preprocessor_name: str | None
    preprocessor_version: str | None
    model_name: str | None
    model_parameters: JsonObject | None
    primary_metric: str = "macro_f1"
    output_directory: str

    _nonblank_run_id = field_validator("run_id")(require_nonblank)
    _aware_created_at = field_validator("created_at")(require_aware_datetime)
    _nonblank_metric = field_validator("primary_metric")(require_nonblank)
    _nonblank_output = field_validator("output_directory")(require_nonblank)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (not value or any(not part for part in value)):
            raise ValueError("command must be null or a nonempty argv list")
        return value

    @field_validator("git_commit")
    @classmethod
    def validate_git_commit(cls, value: str | None) -> str | None:
        if value is not None:
            if not 7 <= len(value) <= 40 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("git_commit must be 7-40 lowercase hexadecimal characters")
        return value

    @field_validator("dependency_versions")
    @classmethod
    def validate_dependency_versions(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        if value is not None and any(not key or not version for key, version in value.items()):
            raise ValueError("package names and versions must be nonempty")
        return value

    @field_validator("model_parameters")
    @classmethod
    def validate_model_params(cls, value: JsonObject | None) -> JsonObject | None:
        if value is not None:
            try:
                json.dumps(value, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "model_parameters must be strict JSON-compatible data"
                ) from exc
        return value
