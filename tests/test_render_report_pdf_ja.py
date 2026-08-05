"""Regression guard: the Japanese PDF-only re-render path must not apply
the English track's configs/report_layout_overrides.json.

That file's page_break_before IDs ("heading-6", "heading-9", a content-hash
ID for the English "Technical Appendix" heading) were authored for the
English report's specific heading structure. Applying it to the Japanese
report -- a different number/order/wording of headings -- forces a page
break at whatever heading happens to occupy that position/hash by
coincidence. Caught empirically: running the English
scripts/render_report_pdf.py against the Japanese report directory changed
its page count from 11 (the reviewed, hash-recorded version) to 12 with no
change to report.md itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mail_classification.reporting import render_report_pdf

ROOT = Path(__file__).parents[1]
REPORT_DIR = ROOT / "outputs" / "reports" / "phaseJA9-report-phaseJA4-core-seed42"
ENGLISH_OVERRIDES_PATH = ROOT / "configs" / "report_layout_overrides.json"


def _require_report_artifacts() -> None:
    if not (REPORT_DIR / "report.md").is_file():
        pytest.skip("Phase JA-9 report artifacts are not generated locally")


def test_render_report_pdf_ja_script_does_not_reference_english_overrides() -> None:
    source = (ROOT / "scripts" / "render_report_pdf_ja.py").read_text(encoding="utf-8")
    assert "DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH" not in source
    assert "layout_overrides_path=None" in source


def test_rendering_ja_report_without_overrides_matches_write_report_ja_page_count() -> None:
    """The page count produced by the JA-safe re-render path (no overrides)
    must match write_report_ja()'s own output, and must NOT match what the
    English overrides file would produce (12 pages, verified manually while
    diagnosing this bug)."""
    _require_report_artifacts()
    markdown_path = REPORT_DIR / "report.md"

    _, _, pdf_path, layout_check_path = render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=None
    )
    import json

    layout_check = json.loads(layout_check_path.read_text(encoding="utf-8"))
    assert layout_check["status"] == "PASS"
    assert layout_check["violations"] == []
    assert layout_check["page_count"] == 11
    assert pdf_path.is_file()


def test_english_overrides_file_is_not_silently_reused_for_japanese_report() -> None:
    """Applying the English overrides to the Japanese report changes its
    page count -- this is the actual regression this whole test module
    exists to prevent from happening unnoticed via the wrong script."""
    _require_report_artifacts()
    if not ENGLISH_OVERRIDES_PATH.is_file():
        pytest.skip("configs/report_layout_overrides.json is not present")
    markdown_path = REPORT_DIR / "report.md"

    _, _, _, layout_check_path = render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=ENGLISH_OVERRIDES_PATH
    )
    import json

    layout_check = json.loads(layout_check_path.read_text(encoding="utf-8"))
    assert layout_check["page_count"] != 11  # demonstrates the mismatch

    # Restore the correct (no-overrides) PDF so this test doesn't leave the
    # tracked report_decision hash stale for anyone running the suite.
    render_report_pdf(markdown_path, REPORT_DIR, layout_overrides_path=None)
