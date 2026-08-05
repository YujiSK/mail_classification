"""Regression guard: the Japanese PDF render path must use
configs/report_layout_overrides_ja.json (Japanese-specific heading IDs),
and must NEVER apply the English track's configs/report_layout_overrides.json.

The English file's page_break_before IDs ("heading-6", "heading-9", a
content-hash ID for the English "Technical Appendix" heading) were authored
for the English report's specific heading structure. Applying it to the
Japanese report -- a different number/order/wording of headings -- forces a
page break at whatever heading happens to occupy that position/hash by
coincidence. Caught empirically: running the English
scripts/render_report_pdf.py against the Japanese report directory changed
its page count from 11 (the reviewed, hash-recorded version) to 12 with no
change to report.md itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mail_classification.reporting import render_report_pdf
from mail_classification.reporting.ja_generation import (
    DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA,
)

ROOT = Path(__file__).parents[1]
REPORT_DIR = ROOT / "outputs" / "reports" / "phaseJA9-report-phaseJA4-core-seed42"
ENGLISH_OVERRIDES_PATH = ROOT / "configs" / "report_layout_overrides.json"


def _require_report_artifacts() -> None:
    if not (REPORT_DIR / "report.md").is_file():
        pytest.skip("Phase JA-9 report artifacts are not generated locally")


def test_ja_layout_overrides_file_exists_and_is_japanese_specific() -> None:
    assert DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA.is_file()
    assert DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA.name == "report_layout_overrides_ja.json"
    assert DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA != ENGLISH_OVERRIDES_PATH


def test_render_report_pdf_ja_script_never_references_english_overrides() -> None:
    import re

    source = (ROOT / "scripts" / "render_report_pdf_ja.py").read_text(encoding="utf-8")
    assert "DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA" in source
    # The English module-level constant name must never appear on its own
    # (only as a substring of the "_JA"-suffixed Japanese constant above).
    bare_english_references = re.findall(
        r"DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH(?!_JA)", source
    )
    assert bare_english_references == []


def test_rendering_ja_report_applies_japanese_overrides_by_default() -> None:
    """The JA-safe re-render path must reproduce the same layout_check
    result (PASS, 0 violations) as write_report_ja()'s own default, using
    configs/report_layout_overrides_ja.json."""
    _require_report_artifacts()
    markdown_path = REPORT_DIR / "report.md"

    _, _, pdf_path, layout_check_path = render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )
    import json

    layout_check = json.loads(layout_check_path.read_text(encoding="utf-8"))
    assert layout_check["status"] == "PASS"
    assert layout_check["violations"] == []
    assert pdf_path.is_file()


def test_chapter_5_starts_a_new_page_per_configured_override() -> None:
    """configs/report_layout_overrides_ja.json currently forces a page break
    before heading-5 (第5章 Core実験結果); verify that heading actually
    starts a fresh PDF page, not merely that layout_check passes."""
    _require_report_artifacts()
    pdfplumber = pytest.importorskip("pdfplumber")
    markdown_path = REPORT_DIR / "report.md"
    render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )

    with pdfplumber.open(REPORT_DIR / "report.pdf") as pdf:
        found = False
        for page in pdf.pages:
            text = (page.extract_text() or "").lstrip()
            if text.startswith("第5章"):
                found = True
                break
        assert found, "第5章 does not start at the top of any page"


def test_english_overrides_file_is_not_silently_reused_for_japanese_report() -> None:
    """Applying the English overrides to the Japanese report produces a
    different layout_check outcome than the Japanese-specific overrides --
    this is the actual regression this whole test module exists to prevent
    from happening unnoticed via the wrong script/config."""
    _require_report_artifacts()
    if not ENGLISH_OVERRIDES_PATH.is_file():
        pytest.skip("configs/report_layout_overrides.json is not present")
    markdown_path = REPORT_DIR / "report.md"

    _, _, _, ja_layout_check_path = render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )
    import json

    ja_page_count = json.loads(ja_layout_check_path.read_text(encoding="utf-8"))["page_count"]

    _, _, _, en_layout_check_path = render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=ENGLISH_OVERRIDES_PATH
    )
    en_page_count = json.loads(en_layout_check_path.read_text(encoding="utf-8"))["page_count"]

    assert en_page_count != ja_page_count  # demonstrates the mismatch

    # Restore the correct (Japanese-overrides) PDF so this test doesn't leave
    # the tracked report_decision hash stale for anyone running the suite.
    render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )
