"""Build the Task 10 report (Markdown -> HTML -> PDF -> layout check) from the
fixed, already-verified Phase 4/5/6 runs. Never re-runs training."""

from pathlib import Path
import sys

# Running this file directly puts scripts/ (not the project root) on
# sys.path[0], but mail_classification.reporting imports tools.pdf_renderer,
# which lives at the project root and is not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.reporting import write_report


if __name__ == "__main__":
    result = write_report(Path(__file__).parents[1])
    print(f"report.md: {result.markdown_path}")
    print(f"report.pdf: {result.pdf_path}")
    print(f"layout_check.json: {result.layout_check_path}")
    print(f"manifest.json: {result.manifest_path}")
