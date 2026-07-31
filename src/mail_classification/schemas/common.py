"""Validation primitives shared by artifact schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import Field

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
JsonObject = dict[str, Any]


def require_aware_datetime(value: datetime) -> datetime:
    """Reject naive datetimes so manifests are unambiguous across machines."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a UTC offset")
    return value


def require_nonblank(value: str) -> str:
    """Validate content without changing the original string."""
    if not value.strip():
        raise ValueError("value must not be empty or whitespace-only")
    return value
