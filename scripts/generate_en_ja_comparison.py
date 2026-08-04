"""Generate the Phase JA-8 English<->Japanese Core comparison artifact."""

from pathlib import Path
import sys

# See scripts/build_report.py: mail_classification.reporting imports
# tools.pdf_renderer, which lives at the project root and is not an
# installed package, so the root must be on sys.path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mail_classification.reporting.ja_en_comparison import write_en_ja_comparison


if __name__ == "__main__":
    root = Path(__file__).parents[1]
    output_path = root / "outputs" / "runs" / "phaseJA8-en-ja-comparison-seed42.json"
    comparison = write_en_ja_comparison(root, output_path)
    print(f"written to {output_path}")
    print(f"EN best: {comparison['en_condition']} macro_f1={comparison['en_macro_f1']:.4f}")
    print(f"JA best: {comparison['ja_condition']} macro_f1={comparison['ja_macro_f1']:.4f}")
    print(
        f"both_high={comparison['both_high']} en_only={comparison['en_only_high']} "
        f"ja_only={comparison['ja_only_high']} both_low={comparison['both_low']}"
    )
