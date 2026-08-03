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

__all__ = [
    "DEFAULT_BERT_RUN_ID",
    "ReportBuildResult",
    "macro_f1_comparison_svg",
    "render_report_pdf",
    "svg_bar_chart",
    "verify_selected_runs_consistent",
    "write_report",
]
