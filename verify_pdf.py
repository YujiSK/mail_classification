"""Verify the standalone Markdown -> HTML -> PDF conversion path."""

from __future__ import annotations

from pathlib import Path

from tools.pdf_renderer.reporting import pdf_renderer, report_builder


def main() -> int:
    project_root = Path.cwd().resolve()
    markdown_path = project_root / "outputs" / "test_report.md"
    output_path = project_root / "outputs" / "test_report.pdf"
    css_path = project_root / "tools" / "pdf_renderer" / "assets" / "styles" / "report.css"
    build_dir = project_root / "outputs" / "renders" / "_build"

    html_path, registry_path = report_builder.build(
        md_path=markdown_path,
        css_path=css_path,
        build_dir=build_dir,
    )
    pdf_renderer.render_html_to_pdf(
        html_path=html_path,
        pdf_path=output_path,
        document_root=project_root / "outputs",
    )

    print(f"HTML: {html_path}")
    print(f"Registry: {registry_path}")
    print(f"PDF: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
