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
change to report.md itself. (The Japanese overrides file now also forces
5 page breaks of its own, so page *count* alone no longer distinguishes the
two files reliably -- see
test_english_overrides_file_is_not_silently_reused_for_japanese_report,
which compares actual per-page break positions instead.)
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


def test_configured_headings_each_start_a_new_page() -> None:
    """Every heading text configured in
    configs/report_layout_overrides_ja.json's page_break_before list must
    actually start a fresh PDF page, not merely make layout_check pass."""
    _require_report_artifacts()
    pdfplumber = pytest.importorskip("pdfplumber")
    markdown_path = REPORT_DIR / "report.md"
    render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )

    import json

    registry = json.loads(
        (REPORT_DIR / "_build" / "report.source_registry.json").read_text(encoding="utf-8")
    )
    overrides = json.loads(
        DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA.read_text(encoding="utf-8")
    )
    heading_texts = [
        h["text"]
        for h in registry
        if isinstance(h, dict) and h.get("id") in overrides["page_break_before"]
    ]
    assert len(heading_texts) == len(overrides["page_break_before"])

    with pdfplumber.open(REPORT_DIR / "report.pdf") as pdf:
        page_starts = [(page.extract_text() or "").lstrip() for page in pdf.pages]

    for heading_text in heading_texts:
        # Use a short prefix, not the full heading text: pdfplumber's
        # extraction substitutes some kanji/punctuation with visually
        # identical CJK compatibility codepoints (e.g. 日 -> ⽇, ・ -> ‧)
        # depending on font subsetting, so exact/long-text matches are
        # unreliable even though the rendered page is correct.
        prefix = heading_text[:4]
        assert any(
            start.startswith(prefix) for start in page_starts
        ), f"{heading_text!r} does not start at the top of any page"


def test_english_overrides_file_is_not_silently_reused_for_japanese_report() -> None:
    """Applying the English overrides to the Japanese report forces page
    breaks at different points than the Japanese-specific overrides --
    this is the actual regression this whole test module exists to prevent
    from happening unnoticed via the wrong script/config. (Total page count
    alone is not a reliable signal here: both files happen to yield the same
    page count while breaking at different headings, so this compares the
    actual per-page break positions.)"""
    _require_report_artifacts()
    if not ENGLISH_OVERRIDES_PATH.is_file():
        pytest.skip("configs/report_layout_overrides.json is not present")
    pdfplumber = pytest.importorskip("pdfplumber")
    markdown_path = REPORT_DIR / "report.md"

    render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )
    with pdfplumber.open(REPORT_DIR / "report.pdf") as pdf:
        ja_page_starts = [(page.extract_text() or "").lstrip()[:10] for page in pdf.pages]

    render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=ENGLISH_OVERRIDES_PATH
    )
    with pdfplumber.open(REPORT_DIR / "report.pdf") as pdf:
        en_page_starts = [(page.extract_text() or "").lstrip()[:10] for page in pdf.pages]

    assert en_page_starts != ja_page_starts  # demonstrates the mismatch

    # Restore the correct (Japanese-overrides) PDF so this test doesn't leave
    # the tracked report_decision hash stale for anyone running the suite.
    render_report_pdf(
        markdown_path, REPORT_DIR, layout_overrides_path=DEFAULT_REPORT_LAYOUT_OVERRIDES_PATH_JA
    )
