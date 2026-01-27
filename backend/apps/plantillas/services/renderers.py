from __future__ import annotations

from typing import Any, Dict, List

from django.template import Context, Template

try:
    from weasyprint import HTML, CSS
except ImportError:  # pragma: no cover - fallback for missing dependency
    HTML = None
    CSS = None


def render_html(template_html: str, context: Dict[str, Any]) -> str:
    template = Template(template_html)
    return template.render(Context(context))


def render_pdf(template_html: str, css: str, context: Dict[str, Any]) -> bytes:
    if HTML is None:
        raise RuntimeError("WeasyPrint no está instalado en el entorno.")
    rendered_html = render_html(template_html, context)
    html_obj = HTML(string=rendered_html)
    stylesheets = [CSS(string=css)] if css else []
    return html_obj.write_pdf(stylesheets=stylesheets)


def render_receipt(template_text: str, context: Dict[str, Any]) -> str:
    template = Template(template_text)
    return template.render(Context(context))


def receipt_lines(rendered_text: str) -> List[str]:
    return [line for line in rendered_text.splitlines() if line.strip() != ""]
