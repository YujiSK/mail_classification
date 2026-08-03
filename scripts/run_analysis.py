"""Run the Fold-imbalance and structural-ratio analyses used by the Phase 7
report's Chapter 3/4 discussion. Never re-trains a model; reads only
outputs/folds/common_folds.json, data/raw/full_emails.jsonl, and
outputs/runs/<explain_run_id>/misclassifications.csv."""

from pathlib import Path
import sys

# Running this file directly puts scripts/ (not the project root) on
# sys.path[0], but mail_classification.reporting imports tools.pdf_renderer,
# which lives at the project root and is not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.analysis import (
    write_fold_imbalance_stats,
    write_structural_ratio_comparison,
)
from mail_classification.reporting.generation import DEFAULT_EXPLAIN_RUN_ID

if __name__ == "__main__":
    project_root = Path(__file__).parents[1]
    fold_artifact_path = project_root / "outputs" / "folds" / "common_folds.json"
    full_data_path = project_root / "data" / "raw" / "full_emails.jsonl"
    misclassifications_path = (
        project_root / "outputs" / "runs" / DEFAULT_EXPLAIN_RUN_ID / "misclassifications.csv"
    )

    fold_imbalance_path = write_fold_imbalance_stats(
        fold_artifact_path,
        full_data_path,
        project_root / "outputs" / "analysis" / "fold_imbalance_stats.csv",
    )
    print(f"fold_imbalance_stats.csv: {fold_imbalance_path}")

    structural_ratio_path = write_structural_ratio_comparison(
        full_data_path,
        misclassifications_path,
        project_root / "outputs" / "analysis" / "structural_ratio_comparison.json",
    )
    print(f"structural_ratio_comparison.json: {structural_ratio_path}")
