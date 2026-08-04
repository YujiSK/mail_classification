"""Phase 7 reporting: reads saved Core/Explain/Extension artifacts only, never
re-runs training, and drives tools/pdf_renderer for the final PDF."""

from .figures import macro_f1_comparison_svg, svg_bar_chart
from .generation import (
    DEFAULT_BERT_RUN_ID,
    ReportBuildResult,
    render_report_pdf,
    verify_selected_runs_consistent,
    write_report,
)
from .ja_en_comparison import build_en_ja_comparison, write_en_ja_comparison
from .ja_figures import macro_f1_comparison_svg_ja
from .ja_generation import (
    DEFAULT_BERT_RUN_ID as DEFAULT_BERT_RUN_ID_JA,
    ReportBuildResultJa,
    verify_selected_runs_consistent_ja,
    write_report_ja,
)

__all__ = [
    "DEFAULT_BERT_RUN_ID",
    "DEFAULT_BERT_RUN_ID_JA",
    "ReportBuildResult",
    "ReportBuildResultJa",
    "build_en_ja_comparison",
    "macro_f1_comparison_svg",
    "macro_f1_comparison_svg_ja",
    "render_report_pdf",
    "svg_bar_chart",
    "verify_selected_runs_consistent",
    "verify_selected_runs_consistent_ja",
    "write_en_ja_comparison",
    "write_report",
    "write_report_ja",
]
