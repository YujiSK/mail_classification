"""Run the subtopic-contamination Extension end to end on the approved Full
dataset: build the C0/C10/C20/C30 datasets, fit/predict every (contamination
level x condition x model) cell on the existing common Fold artifact, and
write every artifact under outputs/extensions/. Never touches Core's
outputs/runs/, outputs/data_quality/, outputs/folds/, or data/raw/."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.evaluation import load_verified_full_dataset
from mail_classification.extensions.subtopic_contamination import (
    run_and_write_subtopic_contamination_extension,
)

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    full_data_path = project_root / "data" / "raw" / "full_emails.jsonl"
    decision_path = project_root / "docs" / "reviews" / "full_review_decision.json"
    fold_artifact_path = project_root / "outputs" / "folds" / "common_folds.json"

    records = load_verified_full_dataset(full_data_path, decision_path)
    run_dir = run_and_write_subtopic_contamination_extension(
        records, fold_artifact_path, project_root, seed=42
    )
    print(f"run_dir: {run_dir}")
