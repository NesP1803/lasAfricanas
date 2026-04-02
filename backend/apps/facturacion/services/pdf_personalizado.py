"""Generación de PDF personalizado local para factura electrónica."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica


def _build_pdf_bytes(factura: FacturaElectronica) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception:  # pragma: no cover - fallback cuando reportlab no está disponible
        return (
            f'Factura {factura.number}\n'
            f'CUFE: {factura.cufe}\n'
            f'Cliente: {factura.venta.cliente.nombre}\n'
            f'Total: {factura.venta.total}\n'
        ).encode('utf-8')

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y = 760
    lines = [
        'LAS AFRICANAS - FACTURA ELECTRÓNICA',
        f'Número: {factura.number}',
        f'CUFE: {factura.cufe}',
        f'Cliente: {factura.venta.cliente.nombre}',
        f'Documento: {factura.venta.cliente.numero_documento}',
        f'Fecha: {timezone.localtime(factura.created_at).strftime("%Y-%m-%d %H:%M")}',
        f'Resolución: {factura.reference_code or "N/D"}',
        f'Total: {factura.venta.total}',
        'Representación gráfica de factura electrónica.',
    ]
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 18
    y -= 8
    for detalle in factura.venta.detalles.select_related('producto').all():
        pdf.drawString(
            50,
            y,
            f'- {detalle.producto.nombre} x {detalle.cantidad} = {detalle.total}',
        )
        y -= 16
        if y < 60:
            pdf.showPage()
            y = 760
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def generar_pdf_personalizado(factura: FacturaElectronica) -> str:
    """Genera el PDF local usando el diseño del sistema (representación gráfica local)."""
    content = _build_pdf_bytes(factura)
    filename = f'{factura.number or factura.reference_code or factura.id}.pdf'
    relative_path = Path('facturas/pdf_personalizado') / filename
    absolute_path = Path(settings.MEDIA_ROOT) / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    factura.pdf_local_path = str(relative_path)
    factura.save(update_fields=['pdf_local_path', 'updated_at'])
    return factura.pdf_local_path
