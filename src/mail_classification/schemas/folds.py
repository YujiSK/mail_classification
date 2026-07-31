"""Reusable fold-assignment artifact contract (not a splitter)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import Sha256Hex, require_aware_datetime, require_nonblank
from .dataset import MailLabel


class FoldRole(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"


class FoldRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str
    fold_id: int = Field(ge=0)
    split_role: FoldRole
    label: MailLabel
    template_group: str

    _nonblank_sample = field_validator("sample_id")(require_nonblank)
    _nonblank_group = field_validator("template_group")(require_nonblank)


class FoldMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    created_at: datetime
    splitter_name: str
    n_splits: int = Field(ge=2)
    random_seed: int = Field(ge=0)
    label_column: str = "label"
    group_column: str = "template_group"
    data_hash: Sha256Hex

    _aware_created_at = field_validator("created_at")(require_aware_datetime)
    _nonblank_splitter = field_validator("splitter_name")(require_nonblank)
    _nonblank_label = field_validator("label_column")(require_nonblank)
    _nonblank_group = field_validator("group_column")(require_nonblank)


class FoldArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: FoldMetadata
    records: list[FoldRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_assignments(self) -> "FoldArtifact":
        seen: set[tuple[int, str]] = set()
        group_roles: dict[tuple[int, str], set[FoldRole]] = {}
        for record in self.records:
            if record.fold_id >= self.metadata.n_splits:
                raise ValueError("fold_id must be smaller than n_splits")
            sample_key = (record.fold_id, record.sample_id)
            if sample_key in seen:
                raise ValueError(
                    "a sample may appear only once per fold and cannot cross roles"
                )
            seen.add(sample_key)
            group_roles.setdefault(
                (record.fold_id, record.template_group), set()
            ).add(record.split_role)
        if any(len(roles) > 1 for roles in group_roles.values()):
            raise ValueError(
                "template_group cannot be split between train and validation in a fold"
            )
        return self
