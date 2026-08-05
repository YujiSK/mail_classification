"""Cross-label near-duplicate sensitivity, reusing the Phase 6 MinHashLSH Extension as-is.

Answers the "cross-label近接重複" quality-audit requirement: after subtopic
sentences are mixed in, does any contaminated record become a near-duplicate
of a record carrying a *different* label? A nonzero ``cross_label_pairs``
count would be a design smell (the inserted sentence made the whole email
read like the subtopic's class), not proof of statistical leakage by itself.
"""

from __future__ import annotations

from mail_classification.schemas import RawMailRecord

from ..minhash import find_near_duplicates, summarize_near_duplicates


def cross_label_near_duplicate_summary(records: list[RawMailRecord]) -> dict[str, object]:
    rows = find_near_duplicates(records)
    return summarize_near_duplicates(rows)
