"""Render an existing report.md -> HTML -> PDF -> layout check, AS-IS.

Unlike scripts/build_report.py, this never regenerates report.md's content
from the CSV/JSON artifacts -- it only converts whatever is currently on
disk. Use this after hand-editing report.md for final wording/polish.

Note: any number or claim you hand-edit into report.md this way is no
longer traceable to a source artifact. Re-run scripts/build_report.py
instead whenever you need the report to reflect updated artifact values.
"""

import argparse
from pathlib import Path
import sys

# Running this file directly puts scripts/ (not the project root) on
# sys.path[0], but mail_classification.reporting imports tools.pdf_renderer,
# which lives at the project root and is not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.reporting import render_report_pdf

DEFAULT_REPORT_DIR = "outputs/reports/phase7-report-phase4-core-seed42"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report_dir",
        nargs="?",
        default=DEFAULT_REPORT_DIR,
        help=f"Directory containing report.md, relative to the project root (default: {DEFAULT_REPORT_DIR})",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    report_dir = (project_root / args.report_dir).resolve()
    markdown_path = report_dir / "report.md"
    if not markdown_path.is_file():
        raise FileNotFoundError(f"{markdown_path} does not exist")

    html_path, registry_path, pdf_path, layout_check_path = render_report_pdf(
        markdown_path, report_dir
    )
    print(f"report.pdf: {pdf_path}")
    print(f"layout_check.json: {layout_check_path}")
