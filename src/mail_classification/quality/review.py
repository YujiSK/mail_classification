"""Deterministic selection of Pilot records for human review."""

from __future__ import annotations

from collections import defaultdict

from mail_classification.schemas import Difficulty, MailLabel, RawMailRecord

REVIEW_FIELDS = [
    "id",
    "raw_text",
    "body_text",
    "label",
    "difficulty",
    "template_group",
    "template_id",
    "variation_id",
    "selection_reasons",
    "review_status",
    "review_comment",
]


def build_review_samples(
    records: list[RawMailRecord],
    per_label: int,
    duplicate_findings: list[dict[str, object]],
    leakage_findings: list[dict[str, object]],
) -> list[dict[str, object]]:
    reasons: dict[str, set[str]] = defaultdict(set)
    by_label = defaultdict(list)
    for record in sorted(records, key=lambda item: item.id):
        by_label[record.label].append(record)
    for label in MailLabel:
        for record in by_label[label][:per_label]:
            reasons[record.id].add(f"class_sample:{label.value}")

    for difficulty in Difficulty:
        match = next((item for item in records if item.difficulty == difficulty), None)
        if match:
            reasons[match.id].add(f"difficulty:{difficulty.value}")

    shortest = min(records, key=lambda item: len(item.raw_text))
    longest = max(records, key=lambda item: len(item.raw_text))
    reasons[shortest.id].add("shortest")
    reasons[longest.id].add("longest")
    for field, reason in (
        ("contains_negation", "negation"),
        ("multi_intent", "multi_intent"),
    ):
        for record in records:
            if record.metadata.get(field):
                reasons[record.id].add(reason)
                break
    for field in ("has_header", "has_signature", "has_quoted_reply"):
        match = next((item for item in records if getattr(item, field)), None)
        if match:
            reasons[match.id].add(field)

    for finding in duplicate_findings:
        for record_id in str(finding["record_ids"]).split("|"):
            if record_id:
                reasons[record_id].add("duplicate_finding")
    for finding in leakage_findings:
        for record_id in str(finding["record_ids"]).split("|"):
            if record_id:
                reasons[record_id].add("leakage_finding")

    by_id = {record.id: record for record in records}
    rows = []
    for record_id in sorted(reasons):
        record = by_id[record_id]
        rows.append(
            {
                "id": record.id,
                "raw_text": record.raw_text,
                "body_text": record.body_text,
                "label": record.label.value,
                "difficulty": record.difficulty.value,
                "template_group": record.template_group,
                "template_id": record.template_id,
                "variation_id": record.variation_id,
                "selection_reasons": "|".join(sorted(reasons[record_id])),
                "review_status": "",
                "review_comment": "",
            }
        )
    return rows


def build_full_spot_review_samples(
    records: list[RawMailRecord],
    leakage_findings: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Select exactly one review record per template group for Full QA."""
    if not records:
        raise ValueError("Full spot review requires records")

    by_group: dict[str, list[RawMailRecord]] = defaultdict(list)
    for record in sorted(records, key=lambda item: item.id):
        by_group[record.template_group].append(record)
    selected = {group: matches[0] for group, matches in by_group.items()}

    shortest = min(records, key=lambda item: len(item.raw_text))
    longest = max(records, key=lambda item: len(item.raw_text))
    selected[shortest.template_group] = shortest
    selected[longest.template_group] = longest

    selected_ids = {record.id for record in selected.values()}
    for finding in leakage_findings:
        finding_ids = set(str(finding["record_ids"]).split("|"))
        if selected_ids & finding_ids:
            continue
        match = next(
            (
                record
                for record in sorted(records, key=lambda item: item.id)
                if record.id in finding_ids
            ),
            None,
        )
        if match is not None:
            previous = selected[match.template_group]
            selected[match.template_group] = match
            selected_ids.discard(previous.id)
            selected_ids.add(match.id)

    chosen = sorted(selected.values(), key=lambda item: item.id)
    reasons: dict[str, set[str]] = defaultdict(set)
    for record in chosen:
        reasons[record.id].update(
            {
                f"class:{record.label.value}",
                f"difficulty:{record.difficulty.value}",
                f"template_group:{record.template_group}",
            }
        )
    reasons[shortest.id].add("shortest")
    reasons[longest.id].add("longest")

    for field, reason in (
        ("contains_negation", "negation"),
        ("multi_intent", "multi_intent"),
    ):
        match = next((item for item in chosen if item.metadata.get(field)), None)
        if match:
            reasons[match.id].add(reason)
    for field in ("has_header", "has_signature", "has_quoted_reply"):
        match = next((item for item in chosen if getattr(item, field)), None)
        if match:
            reasons[match.id].add(field)
    for finding in leakage_findings:
        finding_ids = set(str(finding["record_ids"]).split("|"))
        match = next((item for item in chosen if item.id in finding_ids), None)
        if match:
            reasons[match.id].add(f"leakage_finding:{finding['feature']}")

    rows = []
    for record in chosen:
        rows.append(
            {
                "id": record.id,
                "raw_text": record.raw_text,
                "body_text": record.body_text,
                "label": record.label.value,
                "difficulty": record.difficulty.value,
                "template_group": record.template_group,
                "template_id": record.template_id,
                "variation_id": record.variation_id,
                "selection_reasons": "|".join(sorted(reasons[record.id])),
                "review_status": "",
                "review_comment": "",
            }
        )
    return rows
