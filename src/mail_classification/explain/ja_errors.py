"""Japanese misclassification extraction with an extended error taxonomy.

Extends the English taxonomy (``errors.py``: multi_intent, negation_present,
structural_content, ambiguous_difficulty -- all from Phase 2 generator
metadata) with three Japanese-specific, heuristic categories per explicit
instruction, and stores every category as an independent boolean column
rather than picking one ``primary_category`` per record ("カテゴリは重複可と
し、1件を無理に一つだけへ割り当てないでください"). ``primary_category`` is
still included (first true category by a documented priority order) only as
a convenience for simple summary tables; the boolean columns are the source
of truth for per-category counts.

The three added categories are explicitly heuristic, not generator-recorded
ground truth, and are documented as such:

- ``orthographic_variation``: ``raw_text`` contains a known kanji/kana
  orthographic-variant substring actually authored into the templates
  (e.g. "出来" alongside the more common "できる" spelling used elsewhere in
  the same semantic template group -- see ``tg-ja-019`` in
  ``assets/templates/email_templates_ja.yml``), or mixes full-width and
  half-width alphanumeric characters in the same record.
- ``mixed_ja_en``: ``raw_text`` contains both a Japanese-script run
  (hiragana/katakana/CJK) and a Latin-letter run of 2+ characters (e.g.
  "iPhone 15", "2FA", "URL").
- ``morphological_segmentation``: ``raw_text`` contains a URL or email
  address glued directly to Japanese text with no separating whitespace --
  the concrete boundary condition
  ``docs/contracts/preprocessing_contract_ja.md`` documents as the real
  stress case for Sudachi/regex tokenization in this corpus (see the
  ``\\b``-boundary bug fixed in Phase JA-1).
"""

from __future__ import annotations

from collections import Counter
import re

from mail_classification.schemas import Difficulty, RawMailRecord

from .ja_evidence import EVIDENCE_FIELDS

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
    "cat_multi_intent",
    "cat_negation_present",
    "cat_structural_content",
    "cat_ambiguous_difficulty",
    "cat_orthographic_variation",
    "cat_mixed_ja_en",
    "cat_morphological_segmentation",
    "cat_uncategorized",
    "primary_category",
    "raw_text",
    "processed_text",
    *EVIDENCE_FIELDS,
]

ERROR_CATEGORY_SUMMARY_FIELDS = ["condition", "model", "primary_category", "count"]
ERROR_CATEGORY_COUNTS_FIELDS = ["condition", "model", "category", "count", "share_of_misclassified"]

AMBIGUOUS_DIFFICULTIES = frozenset({Difficulty.HARD.value, Difficulty.AMBIGUOUS.value})

# Priority order for the single-pick primary_category convenience column.
CATEGORY_PRIORITY = (
    "multi_intent",
    "ambiguous_difficulty",
    "structural_content",
    "negation_present",
    "orthographic_variation",
    "mixed_ja_en",
    "morphological_segmentation",
)

_ORTHOGRAPHIC_VARIANT_SUBSTRINGS = ("出来",)
_LATIN_RUN = re.compile(r"[A-Za-z]{2,}")
_JAPANESE_SCRIPT = re.compile(r"[぀-ヿ一-鿿]")
_URL_OR_EMAIL_GLUED_TO_JAPANESE = re.compile(
    r"[぀-ヿ一-鿿](?:https?://|www\.)"
    r"|(?:https?://|www\.)\S*[぀-ヿ一-鿿]"
    r"|[぀-ヿ一-鿿][A-Za-z0-9._%+-]+@"
    r"|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}[぀-ヿ一-鿿]"
)
# Only the Unicode "Fullwidth and Halfwidth Forms" block's ASCII-equivalent
# fullwidth digits/letters (e.g. "１２３", "ＡＢＣ") count as the fullwidth
# side of a fullwidth/halfwidth *alphanumeric* mix. Checking
# `unicodedata.east_asian_width(ch) in ("F", "W")` instead (an earlier
# version of this heuristic did) is wrong: ordinary hiragana/katakana/kanji
# are also width "W" and `str.isalnum()` is also True for them, so that
# check flagged nearly every record that had any ASCII character anywhere
# (e.g. a sender email in a header) -- caught by inspecting the real
# category-count output (~64% orthographic_variation) before trusting it.
_FULLWIDTH_ALNUM = re.compile(r"[０-９Ａ-Ｚａ-ｚ]")
_HALFWIDTH_ALNUM = re.compile(r"[0-9A-Za-z]")


def _has_fullwidth_halfwidth_alnum_mix(text: str) -> bool:
    return bool(_FULLWIDTH_ALNUM.search(text)) and bool(_HALFWIDTH_ALNUM.search(text))


def _is_orthographic_variation(body_text: str) -> bool:
    if any(substring in body_text for substring in _ORTHOGRAPHIC_VARIANT_SUBSTRINGS):
        return True
    return _has_fullwidth_halfwidth_alnum_mix(body_text)


def _is_mixed_ja_en(body_text: str) -> bool:
    # Uses body_text, not raw_text: raw_text's header/signature can contain
    # an ASCII sender email even when the message body itself is pure
    # Japanese, which would falsely count as "mixed language content" (also
    # caught empirically -- an earlier raw_text-based version flagged ~62%
    # of records, dominated by header-only ASCII rather than genuine
    # in-body EN/JA mixing like "iPhone 15" or "2FA").
    return bool(_LATIN_RUN.search(body_text)) and bool(_JAPANESE_SCRIPT.search(body_text))


def _is_morphological_segmentation_risk(body_text: str) -> bool:
    return bool(_URL_OR_EMAIL_GLUED_TO_JAPANESE.search(body_text))


def _category_flags(record: RawMailRecord) -> dict[str, bool]:
    flags = {
        "multi_intent": bool(record.metadata.get("multi_intent")),
        "ambiguous_difficulty": record.difficulty.value in AMBIGUOUS_DIFFICULTIES,
        "structural_content": bool(
            record.has_header or record.has_signature or record.has_quoted_reply
        ),
        "negation_present": bool(record.metadata.get("contains_negation")),
        "orthographic_variation": _is_orthographic_variation(record.body_text),
        "mixed_ja_en": _is_mixed_ja_en(record.body_text),
        "morphological_segmentation": _is_morphological_segmentation_risk(record.body_text),
    }
    flags["uncategorized"] = not any(flags.values())
    return flags


def _primary_category(flags: dict[str, bool]) -> str:
    for category in CATEGORY_PRIORITY:
        if flags[category]:
            return category
    return "uncategorized"


def build_misclassification_rows_ja(
    oof_rows: list[dict[str, object]],
    records_by_id: dict[str, RawMailRecord],
    processed_text_by_condition_and_id: dict[tuple[str, str], str],
) -> list[dict[str, object]]:
    """Extract only true != predicted OOF rows, joined with generator-known and heuristic factors."""
    rows: list[dict[str, object]] = []
    for row in oof_rows:
        if row["true_label"] == row["predicted_label"]:
            continue
        record = records_by_id[row["sample_id"]]
        flags = _category_flags(record)
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
                "cat_multi_intent": flags["multi_intent"],
                "cat_negation_present": flags["negation_present"],
                "cat_structural_content": flags["structural_content"],
                "cat_ambiguous_difficulty": flags["ambiguous_difficulty"],
                "cat_orthographic_variation": flags["orthographic_variation"],
                "cat_mixed_ja_en": flags["mixed_ja_en"],
                "cat_morphological_segmentation": flags["morphological_segmentation"],
                "cat_uncategorized": flags["uncategorized"],
                "primary_category": _primary_category(flags),
                "raw_text": record.raw_text,
                "processed_text": processed_text_by_condition_and_id.get(
                    (row["condition"], row["sample_id"]), ""
                ),
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


ALL_CATEGORIES = (
    "multi_intent",
    "negation_present",
    "structural_content",
    "ambiguous_difficulty",
    "orthographic_variation",
    "mixed_ja_en",
    "morphological_segmentation",
    "uncategorized",
)


def summarize_error_category_counts(
    misclassification_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Per (condition, model, category) count and share, allowing overlap.

    Unlike ``summarize_error_categories`` (single primary_category per row,
    rows partition exactly), this counts every category a row matches, so
    the shares across categories for one (condition, model) can sum to more
    than 1.0 -- that is expected, not a bug, per the explicit instruction
    not to force one-category-per-record.
    """
    totals: Counter[tuple[str, str]] = Counter()
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in misclassification_rows:
        key = (row["condition"], row["model"])
        totals[key] += 1
        for category in ALL_CATEGORIES:
            if row[f"cat_{category}"]:
                counts[(*key, category)] += 1

    rows: list[dict[str, object]] = []
    for (condition, model, category), count in sorted(counts.items()):
        total = totals[(condition, model)]
        rows.append(
            {
                "condition": condition,
                "model": model,
                "category": category,
                "count": count,
                "share_of_misclassified": count / total if total else 0.0,
            }
        )
    return rows
