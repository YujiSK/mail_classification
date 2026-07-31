"""Exact and preprocessing-aligned normalized duplicate detection."""

from __future__ import annotations

from collections import defaultdict
import hashlib

from mail_classification.preprocessing import EnglishPreprocessor
from mail_classification.schemas import RawMailRecord

DUPLICATE_FIELDS = [
    "match_type",
    "source_field",
    "canonical_sha256",
    "record_count",
    "record_ids",
    "labels",
    "template_groups",
]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_duplicates(records: list[RawMailRecord]) -> list[dict[str, object]]:
    preprocessor = EnglishPreprocessor()
    values: dict[tuple[str, str], dict[str, list[RawMailRecord]]] = {}
    for match_type, source_field in (
        ("exact", "raw_text"),
        ("exact", "body_text"),
        ("normalized", "raw_text"),
        ("normalized", "body_text"),
    ):
        groups: dict[str, list[RawMailRecord]] = defaultdict(list)
        for record in records:
            text = getattr(record, source_field)
            canonical = (
                text
                if match_type == "exact"
                else preprocessor.transform(text).clean_text
            )
            groups[canonical].append(record)
        values[(match_type, source_field)] = groups

    findings: list[dict[str, object]] = []
    for (match_type, source_field), groups in values.items():
        for canonical, matches in groups.items():
            if len(matches) < 2:
                continue
            findings.append(
                {
                    "match_type": match_type,
                    "source_field": source_field,
                    "canonical_sha256": _digest(canonical),
                    "record_count": len(matches),
                    "record_ids": "|".join(sorted(item.id for item in matches)),
                    "labels": "|".join(
                        sorted({item.label.value for item in matches})
                    ),
                    "template_groups": "|".join(
                        sorted({item.template_group for item in matches})
                    ),
                }
            )
    return sorted(
        findings,
        key=lambda item: (
            str(item["match_type"]),
            str(item["source_field"]),
            str(item["canonical_sha256"]),
        ),
    )
