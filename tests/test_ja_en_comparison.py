from pathlib import Path

import pytest

from mail_classification.reporting.ja_en_comparison import build_en_ja_comparison

ROOT = Path(__file__).parents[1]


def _require_real_artifacts() -> None:
    en_core = ROOT / "outputs" / "runs" / "phase4-core-seed42"
    ja_core = ROOT / "outputs" / "runs" / "phaseJA4-core-seed42"
    if not (en_core / "manifest.json").is_file() or not (ja_core / "manifest.json").is_file():
        pytest.skip("EN and/or JA Core run artifacts are not generated locally")


def test_build_en_ja_comparison_group_counts_are_consistent() -> None:
    _require_real_artifacts()
    comparison = build_en_ja_comparison(ROOT)

    total_groups = len(comparison["en_group_accuracy"])
    assert total_groups == 24  # 24 semantic_template_id groups
    assert (
        comparison["both_high"]
        + comparison["en_only_high"]
        + comparison["ja_only_high"]
        + comparison["both_low"]
        == total_groups
    )
    assert 0.0 <= comparison["en_macro_f1"] <= 1.0
    assert 0.0 <= comparison["ja_macro_f1"] <= 1.0
    assert all(0.0 <= v <= 1.0 for v in comparison["en_group_accuracy"].values())
    assert all(0.0 <= v <= 1.0 for v in comparison["ja_group_accuracy"].values())


def test_build_en_ja_comparison_groups_are_semantic_template_ids() -> None:
    _require_real_artifacts()
    comparison = build_en_ja_comparison(ROOT)
    expected = {f"tg{index:03d}" for index in range(1, 25)}
    assert set(comparison["en_group_accuracy"]) == expected
    assert set(comparison["ja_group_accuracy"]) == expected
