"""Phase 7 reporting: reads saved Core/Explain/Extension artifacts only, never
re-runs training, and drives tools/pdf_renderer for the final PDF."""

from .figures import macro_f1_comparison_svg, svg_bar_chart
from .generation import ReportBuildResult, verify_selected_runs_consistent, write_report

__all__ = [
    "ReportBuildResult",
    "macro_f1_comparison_svg",
    "svg_bar_chart",
    "verify_selected_runs_consistent",
    "write_report",
]
