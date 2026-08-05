"""Build the subtopic-contamination Extension report (Markdown -> HTML -> PDF ->
layout check) from the already-written run at
outputs/extensions/phase-subtopic-contamination-seed42/. Never re-runs training."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.extensions.subtopic_contamination import (
    write_subtopic_contamination_report,
)

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    result = write_subtopic_contamination_report(project_root)
    print(f"report.md: {result.markdown_path}")
    print(f"report.pdf: {result.pdf_path}")
    print(f"layout_check.json: {result.layout_check_path}")
