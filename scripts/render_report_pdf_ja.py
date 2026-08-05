"""Render an existing Japanese report.md -> HTML -> PDF -> layout check, AS-IS.

Like scripts/render_report_pdf.py, this never regenerates report.md's
content from the CSV/JSON artifacts -- it only converts whatever is
currently on disk. Use this after hand-editing report.md for final
wording/polish.

Deliberately does NOT apply configs/report_layout_overrides.json (unlike
scripts/render_report_pdf.py): that file's page_break_before IDs
("heading-6", "heading-9", a content-hash ID for the English "Technical
Appendix" heading) were authored for the English report's specific heading
structure. Applying it to the Japanese report -- which has a different
number, order, and wording of headings -- forces a page break at whatever
heading happens to occupy that same position/hash by coincidence, not at
any semantically chosen point. This was caught empirically: running
scripts/render_report_pdf.py against the Japanese report directory changed
it from 11 pages (the reviewed, hash-recorded version) to 12 pages with no
change to report.md itself. write_report_ja() already omits the overrides
for the same reason; this script matches that.

If the Japanese report ever needs its own forced page breaks, author a
separate configs/report_layout_overrides_ja.json (keyed to the Japanese
report's own heading registry) rather than reusing the English one.

Note: any number or claim you hand-edit into report.md this way is no
longer traceable to a source artifact. Re-run the Python one-liner that
calls mail_classification.reporting.write_report_ja instead whenever you
need the report to reflect updated artifact values -- see the module
docstring / README reproduction steps.

Note on PDF hashes: the underlying Chrome-based renderer is not
byte-deterministic across runs even for byte-identical report.md input (a
timestamp/font-subsetting/ID artifact varies), so report.pdf's SHA-256 will
differ between two renders of the same content. report.md's SHA-256 is the
stable, meaningful hash to compare for "did the content change"; re-record
report.pdf's SHA-256 in docs/reviews/phaseJA9_report_decision.json after
every re-render, don't expect it to stay fixed.
"""

import argparse
from pathlib import Path
import sys

# Running this file directly puts scripts/ (not the project root) on
# sys.path[0], but mail_classification.reporting imports tools.pdf_renderer,
# which lives at the project root and is not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.reporting import render_report_pdf

DEFAULT_REPORT_DIR = "outputs/reports/phaseJA9-report-phaseJA4-core-seed42"

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
        markdown_path,
        report_dir,
        layout_overrides_path=None,
    )
    print(f"report.pdf: {pdf_path}")
    print(f"layout_check.json: {layout_check_path}")
