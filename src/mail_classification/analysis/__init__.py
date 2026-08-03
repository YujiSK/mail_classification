"""Ad-hoc analysis over already-written Core/Fold artifacts (pandas-based).

Never re-fits/re-derives model predictions or Fold assignments; only reads
outputs/folds/common_folds.json, data/raw/full_emails.jsonl, and
outputs/runs/<explain_run_id>/misclassifications.csv."""

from .fold_imbalance import compute_fold_imbalance_stats, write_fold_imbalance_stats
from .structural_ratio import (
    compute_structural_ratio_comparison,
    write_structural_ratio_comparison,
)

__all__ = [
    "compute_fold_imbalance_stats",
    "compute_structural_ratio_comparison",
    "write_fold_imbalance_stats",
    "write_structural_ratio_comparison",
]
