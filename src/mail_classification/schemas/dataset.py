"""Schema for one immutable synthetic-mail source record."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import JsonObject, require_aware_datetime, require_nonblank


class MailLabel(StrEnum):
    PRODUCT_INQUIRY = "product_inquiry"
    TECHNICAL_ISSUE = "technical_issue"
    BILLING = "billing"
    ACCOUNT_SUPPORT = "account_support"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    AMBIGUOUS = "ambiguous"


class RawMailRecord(BaseModel):
    """Canonical record; ``raw_text`` is required and never normalized."""

    model_config = ConfigDict(extra="forbid")

    id: str
    raw_text: str
    body_text: str
    label: MailLabel
    template_group: str
    difficulty: Difficulty
    has_header: bool
    has_signature: bool
    has_quoted_reply: bool
    generation_seed: int = Field(ge=0)
    template_id: str
    variation_id: int = Field(ge=0)
    generated_at: datetime
    metadata: JsonObject = Field(default_factory=dict)

    _nonblank_id = field_validator("id")(require_nonblank)
    _nonblank_raw = field_validator("raw_text")(require_nonblank)
    _nonblank_body = field_validator("body_text")(require_nonblank)
    _nonblank_group = field_validator("template_group")(require_nonblank)
    _nonblank_template = field_validator("template_id")(require_nonblank)
    _aware_generated_at = field_validator("generated_at")(require_aware_datetime)

    @field_validator("metadata")
    @classmethod
    def validate_metadata_json(cls, value: JsonObject) -> JsonObject:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be strict JSON-compatible data") from exc
        return value
