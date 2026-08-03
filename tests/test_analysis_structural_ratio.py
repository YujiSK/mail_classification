import json
from pathlib import Path

import pytest

from mail_classification.analysis import (
    compute_structural_ratio_comparison,
    write_structural_ratio_comparison,
)


def _write_full_dataset(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _write_misclassifications(path: Path, rows: list[dict]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sample_id", "has_header", "has_signature", "has_quoted_reply"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_compute_structural_ratio_comparison_matches_population_when_proportional(
    tmp_path: Path,
) -> None:
    full_path = tmp_path / "full_emails.jsonl"
    _write_full_dataset(
        full_path,
        [
            {"id": f"s{i}", "has_header": i % 2 == 0, "has_signature": False, "has_quoted_reply": False}
            for i in range(10)
        ],
    )
    misclass_path = tmp_path / "misclassifications.csv"
    _write_misclassifications(
        misclass_path,
        [
            {"sample_id": "s0", "has_header": "True", "has_signature": "False", "has_quoted_reply": "False"},
            {"sample_id": "s1", "has_header": "False", "has_signature": "False", "has_quoted_reply": "False"},
        ],
    )

    result = compute_structural_ratio_comparison(full_path, misclass_path)

    assert result["population_total"] == 10
    assert result["misclassified_total"] == 2
    assert result["flags"]["has_header"]["population_ratio"] == pytest.approx(0.5)
    assert result["flags"]["has_header"]["misclassified_ratio"] == pytest.approx(0.5)
    assert result["flags"]["has_header"]["ratio_difference"] == pytest.approx(0.0)
    assert result["flags"]["has_header"]["two_proportion_z_p_value"] == pytest.approx(1.0)


def test_compute_structural_ratio_comparison_detects_enrichment(tmp_path: Path) -> None:
    full_path = tmp_path / "full_emails.jsonl"
    _write_full_dataset(
        full_path,
        [
            {"id": f"s{i}", "has_header": i < 10, "has_signature": False, "has_quoted_reply": False}
            for i in range(100)
        ],
    )
    misclass_path = tmp_path / "misclassifications.csv"
    _write_misclassifications(
        misclass_path,
        [
            {"sample_id": f"m{i}", "has_header": "True", "has_signature": "False", "has_quoted_reply": "False"}
            for i in range(20)
        ],
    )

    result = compute_structural_ratio_comparison(full_path, misclass_path)
    stats = result["flags"]["has_header"]
    assert stats["population_ratio"] == pytest.approx(0.10)
    assert stats["misclassified_ratio"] == pytest.approx(1.0)
    assert stats["exceeds_population_ratio"] is True
    assert stats["two_proportion_z_p_value"] < 0.05


def test_compute_structural_ratio_comparison_rejects_empty_inputs(tmp_path: Path) -> None:
    full_path = tmp_path / "full_emails.jsonl"
    _write_full_dataset(full_path, [])
    misclass_path = tmp_path / "misclassifications.csv"
    _write_misclassifications(misclass_path, [])

    with pytest.raises(ValueError, match="nonempty"):
        compute_structural_ratio_comparison(full_path, misclass_path)


def test_write_structural_ratio_comparison_writes_valid_json(tmp_path: Path) -> None:
    full_path = tmp_path / "full_emails.jsonl"
    _write_full_dataset(
        full_path,
        [{"id": "s0", "has_header": True, "has_signature": True, "has_quoted_reply": False}],
    )
    misclass_path = tmp_path / "misclassifications.csv"
    _write_misclassifications(
        misclass_path,
        [{"sample_id": "s0", "has_header": "True", "has_signature": "True", "has_quoted_reply": "False"}],
    )
    output_path = tmp_path / "outputs" / "analysis" / "structural_ratio_comparison.json"

    result_path = write_structural_ratio_comparison(full_path, misclass_path, output_path)

    assert result_path == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["population_total"] == 1
    assert set(payload["flags"]) == {"has_header", "has_signature", "has_quoted_reply"}


def test_structural_ratio_on_real_full_dataset_and_phase5_misclassifications(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    full_path = root / "data" / "raw" / "full_emails.jsonl"
    misclass_path = root / "outputs" / "runs" / "phase5-explain-seed42" / "misclassifications.csv"
    if not full_path.is_file() or not misclass_path.is_file():
        pytest.skip("Full dataset or Phase 5 misclassifications.csv not present locally")

    output_path = tmp_path / "structural_ratio_comparison.json"
    write_structural_ratio_comparison(full_path, misclass_path, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["population_total"] == 800
    assert payload["misclassified_total"] > 0
    for flag in ("has_header", "has_signature", "has_quoted_reply"):
        stats = payload["flags"][flag]
        assert 0.0 <= stats["population_ratio"] <= 1.0
        assert 0.0 <= stats["misclassified_ratio"] <= 1.0
        assert 0.0 <= stats["two_proportion_z_p_value"] <= 1.0
