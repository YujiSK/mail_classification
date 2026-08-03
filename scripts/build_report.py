"""Build the Task 10 report (Markdown -> HTML -> PDF -> layout check) from the
fixed, already-verified Phase 4/5/6 runs. Never re-runs training."""

from pathlib import Path
import sys

# Running this file directly puts scripts/ (not the project root) on
# sys.path[0], but mail_classification.reporting imports tools.pdf_renderer,
# which lives at the project root and is not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.reporting import DEFAULT_BERT_RUN_ID, write_report


if __name__ == "__main__":
    project_root = Path(__file__).parents[1]
    bert_dir = project_root / "outputs" / "runs" / DEFAULT_BERT_RUN_ID
    bert_run_id = DEFAULT_BERT_RUN_ID if bert_dir.is_dir() else None

    result = write_report(project_root, bert_run_id=bert_run_id)
    print(f"report.md: {result.markdown_path}")
    print(f"report.pdf: {result.pdf_path}")
    print(f"layout_check.json: {result.layout_check_path}")
    print(f"manifest.json: {result.manifest_path}")
