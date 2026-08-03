"""Hand-rolled SVG figure generation (stdlib string formatting only; no plotting dependency).

Mirrors the extensions/minhash.py precedent of avoiding a new third-party
dependency (e.g. matplotlib) when a small amount of from-scratch code covers
the actual need.
"""

from __future__ import annotations

from pathlib import Path

from .tables import CORE_CONDITIONS, CORE_MODELS, read_csv_rows

_WIDTH = 640
_HEIGHT = 380
_MARGIN_TOP = 70
_MARGIN_BOTTOM = 50
_MARGIN_LEFT = 60
_MARGIN_RIGHT = 20
_COLORS = ("#2b6cb0", "#c05621", "#2f855a")


def svg_bar_chart(
    title: str, group_labels: list[str], series: dict[str, list[float]], *, y_max: float | None = None
) -> str:
    """Grouped bar chart. ``series`` maps series name -> one value per group_labels entry."""
    if not group_labels:
        raise ValueError("group_labels must be nonempty")
    for name, values in series.items():
        if len(values) != len(group_labels):
            raise ValueError(f"series {name!r} has {len(values)} values, expected {len(group_labels)}")

    all_values = [v for values in series.values() for v in values]
    resolved_y_max = y_max if y_max is not None else (max(all_values) * 1.15 if all_values else 1.0)

    plot_w = _WIDTH - _MARGIN_LEFT - _MARGIN_RIGHT
    plot_h = _HEIGHT - _MARGIN_TOP - _MARGIN_BOTTOM
    baseline_y = _MARGIN_TOP + plot_h
    n_groups = len(group_labels)
    n_series = max(len(series), 1)
    group_w = plot_w / n_groups
    bar_w = group_w / (n_series + 1)

    legend_parts: list[str] = []
    bar_parts: list[str] = []
    for s_idx, (name, values) in enumerate(series.items()):
        color = _COLORS[s_idx % len(_COLORS)]
        legend_x = _MARGIN_LEFT + s_idx * 150
        legend_parts.append(
            f'<rect x="{legend_x}" y="34" width="12" height="12" fill="{color}" />'
            f'<text x="{legend_x + 16}" y="44" font-size="11" font-family="sans-serif">{name}</text>'
        )
        for g_idx, value in enumerate(values):
            bar_h = plot_h * (value / resolved_y_max) if resolved_y_max else 0.0
            x = _MARGIN_LEFT + g_idx * group_w + (s_idx + 0.5) * bar_w
            y = baseline_y - bar_h
            bar_parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w * 0.8:.1f}" height="{bar_h:.1f}" fill="{color}" />'
            )

    label_parts = [
        f'<text x="{_MARGIN_LEFT + (g_idx + 0.5) * group_w:.1f}" y="{baseline_y + 16:.1f}" '
        f'font-size="11" font-family="sans-serif" text-anchor="middle">{label}</text>'
        for g_idx, label in enumerate(group_labels)
    ]

    axis = (
        f'<line x1="{_MARGIN_LEFT}" y1="{_MARGIN_TOP}" x2="{_MARGIN_LEFT}" y2="{baseline_y}" stroke="black" />'
        f'<line x1="{_MARGIN_LEFT}" y1="{baseline_y}" x2="{_WIDTH - _MARGIN_RIGHT}" y2="{baseline_y}" stroke="black" />'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" '
        f'viewBox="0 0 {_WIDTH} {_HEIGHT}">'
        f'<text x="{_WIDTH / 2}" y="20" font-size="14" font-family="sans-serif" '
        f'text-anchor="middle" font-weight="bold">{title}</text>'
        + "".join(legend_parts)
        + axis
        + "".join(bar_parts)
        + "".join(label_parts)
        + "</svg>"
    )


def macro_f1_comparison_svg(core_run_dir: str | Path) -> str:
    rows = read_csv_rows(Path(core_run_dir) / "metrics_summary.csv")
    by_key = {
        (r["condition"], r["model"]): float(r["cv_mean"])
        for r in rows
        if r["metric"] == "macro_f1"
    }
    series = {
        model: [by_key[(condition, model)] for condition in CORE_CONDITIONS] for model in CORE_MODELS
    }
    return svg_bar_chart(
        "Core macro-F1 (cv_mean) by condition and model",
        list(CORE_CONDITIONS),
        series,
        y_max=1.0,
    )
