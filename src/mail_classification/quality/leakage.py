"""Frequency-based content and metadata leakage audit."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import re

from mail_classification.preprocessing.english import TOKEN_PATTERN
from mail_classification.schemas import MailLabel, RawMailRecord
from mail_classification.generation.models import QualityThresholds

LEAKAGE_FIELDS = [
    "severity",
    "category",
    "feature",
    "labels",
    "count",
    "record_ids",
    "details",
]
HEADER_VALUE = re.compile(r"(?im)^(from|subject):\s*(.+)$")
SIGNATURE = re.compile(r"(?ms)^--\s*$\n(.+?)(?:\n\n|\Z)")


def _finding(
    severity: str,
    category: str,
    feature: str,
    records: list[RawMailRecord],
    details: str,
) -> dict[str, object]:
    return {
        "severity": severity,
        "category": category,
        "feature": feature,
        "labels": "|".join(sorted({record.label.value for record in records})),
        "count": len(records),
        "record_ids": "|".join(sorted(record.id for record in records)),
        "details": details,
    }


def audit_leakage(
    records: list[RawMailRecord], thresholds: QualityThresholds
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    labels = [label.value for label in MailLabel]

    for record in records:
        searchable = "\n".join(
            [
                record.raw_text,
                record.body_text,
                json.dumps(record.metadata, sort_keys=True),
            ]
        ).casefold()
        for label in labels:
            if label in searchable:
                findings.append(
                    _finding(
                        "error",
                        "label_literal",
                        label,
                        [record],
                        "formal label name appears in content or metadata",
                    )
                )
        for identifier in (record.template_id, record.template_group):
            if identifier.casefold() in record.raw_text.casefold():
                findings.append(
                    _finding(
                        "error",
                        "template_literal",
                        identifier,
                        [record],
                        "template identifier appears in raw text",
                    )
                )

    group_records: dict[str, list[RawMailRecord]] = defaultdict(list)
    for record in records:
        group_records[record.template_group].append(record)
    for group, matches in group_records.items():
        group_labels = {record.label for record in matches}
        if len(group_labels) > 1:
            findings.append(
                _finding(
                    "error",
                    "template_group_label_mixing",
                    group,
                    matches,
                    "one template_group contains multiple labels",
                )
            )

    by_label = Counter(record.label.value for record in records)
    for label, count in by_label.items():
        group_count = len(
            {record.template_group for record in records if record.label.value == label}
        )
        largest_group = max(
            Counter(
                record.template_group
                for record in records
                if record.label.value == label
            ).values()
        )
        share = largest_group / count
        if group_count < thresholds.min_template_groups_per_label:
            findings.append(
                _finding(
                    "error",
                    "template_count",
                    label,
                    [record for record in records if record.label.value == label],
                    f"{group_count} groups is below required minimum",
                )
            )
        if share > thresholds.max_template_group_share:
            findings.append(
                _finding(
                    "warning",
                    "template_concentration",
                    label,
                    [record for record in records if record.label.value == label],
                    f"largest group share {share:.3f} exceeds threshold",
                )
            )

    _audit_structural_features(records, findings)
    _audit_shared_component_distribution(
        records,
        findings,
        thresholds.max_shared_component_ratio_deviation,
    )
    _audit_header_and_signature(records, findings, thresholds.exclusive_feature_min_count)
    _audit_exclusive_lexical(records, findings, thresholds.exclusive_feature_min_count)
    _audit_length(records, findings, thresholds.max_length_mean_ratio)
    return sorted(
        findings,
        key=lambda item: (
            str(item["severity"]),
            str(item["category"]),
            str(item["feature"]),
            str(item["record_ids"]),
        ),
    )


def _audit_structural_features(records, findings) -> None:
    for field in ("has_header", "has_signature", "has_quoted_reply", "difficulty"):
        values: dict[str, list[RawMailRecord]] = defaultdict(list)
        for record in records:
            value = getattr(record, field)
            key = value.value if hasattr(value, "value") else str(value)
            values[key].append(record)
        for value, matches in values.items():
            if len({record.label for record in matches}) == 1:
                findings.append(
                    _finding(
                        "warning",
                        "metadata_one_to_one",
                        f"{field}={value}",
                        matches,
                        "metadata value occurs in only one class",
                    )
                )


def _audit_shared_component_distribution(records, findings, maximum_deviation) -> None:
    label_totals = Counter(record.label.value for record in records)
    if len(label_totals) < 2:
        return
    values: dict[object, list[RawMailRecord]] = defaultdict(list)
    for record in records:
        indices = record.metadata.get("component_indices")
        if isinstance(indices, dict) and "urgency" in indices:
            values[indices["urgency"]].append(record)
    for value, matches in values.items():
        counts = Counter(record.label.value for record in matches)
        ratios = {
            label: counts[label] / total
            for label, total in sorted(label_totals.items())
        }
        if max(ratios.values()) - min(ratios.values()) > maximum_deviation:
            findings.append(
                _finding(
                    "warning",
                    "shared_component_distribution",
                    f"urgency={value}",
                    matches,
                    "class occurrence ratios differ beyond the configured threshold: "
                    + json.dumps(ratios, sort_keys=True),
                )
            )


def _audit_header_and_signature(records, findings, minimum) -> None:
    values: dict[tuple[str, str], list[RawMailRecord]] = defaultdict(list)
    for record in records:
        for kind, value in HEADER_VALUE.findall(record.raw_text):
            normalized = value.strip().casefold()
            if kind.casefold() == "from" and "@" in normalized:
                normalized = normalized.rsplit("@", 1)[1]
                kind = "sender_domain"
            values[(kind.casefold(), normalized)].append(record)
        signature = SIGNATURE.search(record.raw_text)
        if signature:
            values[("signature", signature.group(1).strip().casefold())].append(record)
    for (kind, value), matches in values.items():
        if len(matches) >= minimum and len({record.label for record in matches}) == 1:
            findings.append(
                _finding(
                    "warning",
                    f"class_specific_{kind}",
                    value,
                    matches,
                    "repeated structural value occurs in only one class",
                )
            )


def _audit_exclusive_lexical(records, findings, minimum) -> None:
    values: dict[tuple[str, str], list[RawMailRecord]] = defaultdict(list)
    for record in records:
        tokens = [token.casefold() for token in TOKEN_PATTERN.findall(record.body_text)]
        for token in set(tokens):
            values[("token", token)].append(record)
        for bigram in set(zip(tokens, tokens[1:])):
            values[("bigram", " ".join(bigram))].append(record)
    for (kind, feature), matches in values.items():
        if len(matches) >= minimum and len({record.label for record in matches}) == 1:
            findings.append(
                _finding(
                    "info",
                    f"class_specific_{kind}",
                    feature,
                    matches,
                    "candidate for human leakage review; intent words may be legitimate",
                )
            )


def _audit_length(records, findings, maximum_ratio) -> None:
    means = {}
    for label in MailLabel:
        values = [len(record.raw_text) for record in records if record.label == label]
        if values:
            means[label.value] = sum(values) / len(values)
    if means and max(means.values()) / min(means.values()) > maximum_ratio:
        findings.append(
            {
                "severity": "warning",
                "category": "class_length_difference",
                "feature": "raw_text_mean",
                "labels": "|".join(sorted(means)),
                "count": len(records),
                "record_ids": "",
                "details": json.dumps(means, sort_keys=True),
            }
        )
