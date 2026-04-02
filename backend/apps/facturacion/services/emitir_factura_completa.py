"""Orquestador de flujo completo de facturación electrónica con Factus."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.download_invoice_files import download_xml
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient
from apps.facturacion.services.facturar_venta import facturar_venta
from apps.facturacion.services.pdf_personalizado import generar_pdf_personalizado
from apps.usuarios.models import Usuario

logger = logging.getLogger(__name__)


def emitir_factura_completa(venta_id: int, triggered_by: Usuario | None = None) -> dict[str, Any]:
    factura = facturar_venta(venta_id, triggered_by=triggered_by)
    client = FactusClient()
    warnings: list[dict[str, str]] = []

    if factura.status not in {'ACEPTADA', 'EN_PROCESO'}:
        return {'factura': factura, 'warnings': warnings}

    # 1) Sincronizar factura remota.
    try:
        remota = client.get_invoice(factura.number)
        data = remota.get('data', remota)
        bill = data.get('bill', data)
        factura.public_url = str(bill.get('public_url', factura.public_url or '') or factura.public_url or '')
        factura.qr_data = str(bill.get('qr', factura.qr_data or '') or factura.qr_data or '')
        factura.qr_image_url = str(bill.get('qr_image', factura.qr_image_url or '') or factura.qr_image_url or '')
        factura.save(update_fields=['public_url', 'qr_data', 'qr_image_url', 'updated_at'])
    except Exception as exc:
        warnings.append({'component': 'sincronizacion', 'message': str(exc)})

    # 2) XML local.
    try:
        if factura.xml_url:
            download_xml(factura)
        elif factura.number:
            xml_content = client.download_invoice_xml(factura.number)
            xml_filename = f'{factura.number}.xml'
            relative = Path('facturas/xml') / xml_filename
            absolute = Path(settings.MEDIA_ROOT) / relative
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(xml_content)
            factura.xml_local_path = str(relative)
            factura.save(update_fields=['xml_local_path', 'updated_at'])
    except Exception as exc:
        warnings.append({'component': 'xml', 'message': str(exc)})

    # 3) PDF personalizado local.
    try:
        generar_pdf_personalizado(factura)
    except Exception as exc:
        factura.ultimo_error_pdf = str(exc)
        factura.save(update_fields=['ultimo_error_pdf', 'updated_at'])
        warnings.append({'component': 'pdf_local', 'message': str(exc)})

    # 4) Subida de PDF personalizado a Factus.
    try:
        if factura.pdf_local_path:
            local_pdf = (Path(settings.MEDIA_ROOT) / factura.pdf_local_path).read_bytes()
            client.upload_custom_pdf(factura.number, local_pdf, filename=f'{factura.number}.pdf')
            factura.pdf_uploaded_to_factus = True
            factura.pdf_uploaded_at = timezone.now()
            factura.ultimo_error_pdf = ''
            factura.save(update_fields=['pdf_uploaded_to_factus', 'pdf_uploaded_at', 'ultimo_error_pdf', 'updated_at'])
    except (OSError, FactusAPIError, FactusAuthError) as exc:
        factura.pdf_uploaded_to_factus = False
        factura.ultimo_error_pdf = str(exc)
        factura.save(update_fields=['pdf_uploaded_to_factus', 'ultimo_error_pdf', 'updated_at'])
        warnings.append({'component': 'pdf_factus', 'message': str(exc)})

    # 5) Envío de correo por Factus.
    email = str(factura.venta.cliente.email or '').strip()
    if email:
        try:
            client.send_invoice_email(factura.number, email=email)
            factura.correo_enviado = True
            factura.correo_enviado_at = timezone.now()
            factura.ultimo_error_correo = ''
            factura.save(update_fields=['correo_enviado', 'correo_enviado_at', 'ultimo_error_correo', 'updated_at'])
        except (FactusAPIError, FactusAuthError) as exc:
            factura.correo_enviado = False
            factura.ultimo_error_correo = str(exc)
            factura.save(update_fields=['correo_enviado', 'ultimo_error_correo', 'updated_at'])
            warnings.append({'component': 'correo', 'message': str(exc)})

    return {'factura': factura, 'warnings': warnings}
