"""OOF misclassification extraction and a grounded error taxonomy.

Categories come only from fields the Phase 2 generator already records
(``difficulty``, ``metadata["multi_intent"/"secondary_intent"/
"contains_negation"]``, structural flags) — not invented after the fact.
A record can match more than one factor; ``primary_category`` picks one by
priority for a simple summary view, while the individual boolean columns
keep the full picture.
"""

from __future__ import annotations

from collections import Counter

from mail_classification.schemas import Difficulty, RawMailRecord

from .evidence import EVIDENCE_FIELDS

MISCLASSIFICATION_FIELDS = [
    "sample_id",
    "condition",
    "model",
    "fold_id",
    "true_label",
    "predicted_label",
    "difficulty",
    "template_group",
    "has_header",
    "has_signature",
    "has_quoted_reply",
    "multi_intent",
    "secondary_intent",
    "contains_negation",
    "primary_category",
    *EVIDENCE_FIELDS,
]

ERROR_CATEGORY_SUMMARY_FIELDS = ["condition", "model", "primary_category", "count"]

AMBIGUOUS_DIFFICULTIES = frozenset({Difficulty.HARD.value, Difficulty.AMBIGUOUS.value})

# Priority order when more than one factor applies to the same record.
CATEGORY_PRIORITY = (
    "multi_intent",
    "ambiguous_difficulty",
    "structural_content",
    "negation_present",
)


def _primary_category(record: RawMailRecord) -> str:
    if record.metadata.get("multi_intent"):
        return "multi_intent"
    if record.difficulty.value in AMBIGUOUS_DIFFICULTIES:
        return "ambiguous_difficulty"
    if record.has_header or record.has_signature or record.has_quoted_reply:
        return "structural_content"
    if record.metadata.get("contains_negation"):
        return "negation_present"
    return "uncategorized"


def build_misclassification_rows(
    oof_rows: list[dict[str, object]],
    records_by_id: dict[str, RawMailRecord],
) -> list[dict[str, object]]:
    """Extract only true != predicted OOF rows, joined with generator-known factors."""
    rows: list[dict[str, object]] = []
    for row in oof_rows:
        if row["true_label"] == row["predicted_label"]:
            continue
        record = records_by_id[row["sample_id"]]
        rows.append(
            {
                "sample_id": row["sample_id"],
                "condition": row["condition"],
                "model": row["model"],
                "fold_id": row["fold_id"],
                "true_label": row["true_label"],
                "predicted_label": row["predicted_label"],
                "difficulty": record.difficulty.value,
                "template_group": record.template_group,
                "has_header": record.has_header,
                "has_signature": record.has_signature,
                "has_quoted_reply": record.has_quoted_reply,
                "multi_intent": bool(record.metadata.get("multi_intent", False)),
                "secondary_intent": record.metadata.get("secondary_intent"),
                "contains_negation": bool(record.metadata.get("contains_negation", False)),
                "primary_category": _primary_category(record),
            }
        )
    return rows


def summarize_error_categories(
    misclassification_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Count of misclassifications per (condition, model, primary_category)."""
    counter = Counter(
        (row["condition"], row["model"], row["primary_category"])
        for row in misclassification_rows
    )
    return [
        {"condition": condition, "model": model, "primary_category": category, "count": count}
        for (condition, model, category), count in sorted(counter.items())
    ]
