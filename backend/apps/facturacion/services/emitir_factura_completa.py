"""Orquestador de flujo completo de facturación electrónica con Factus."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.download_invoice_files import download_xml
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.facturar_venta import facturar_venta
from apps.facturacion.services.persistence_safety import (
    log_model_string_overflow_diagnostics,
    normalize_qr_image_value,
    safe_assign_charfield,
)
from apps.facturacion.services.upload_custom_pdf_to_factus import (
    send_invoice_email_via_factus,
    upload_custom_pdf_to_factus,
)
from apps.usuarios.models import Usuario

logger = logging.getLogger(__name__)


def emitir_factura_completa(venta_id: int, triggered_by: Usuario | None = None) -> dict[str, Any]:
    factura = facturar_venta(venta_id, triggered_by=triggered_by)
    client = FactusClient()
    warnings: list[dict[str, str]] = []

    estado_electronico = factura.estado_electronico
    if estado_electronico not in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES', 'PENDIENTE_REINTENTO'}:
        return {'factura': factura, 'warnings': warnings}

    # 1) Sincronizar factura remota.
    try:
        remota = client.get_invoice(factura.number)
        data = remota.get('data', remota)
        bill = data.get('bill', data)
        safe_assign_charfield(
            factura,
            'public_url',
            str(bill.get('public_url', factura.public_url or '') or factura.public_url or ''),
        )
        factura.qr_data = str(bill.get('qr', factura.qr_data or '') or factura.qr_data or '')
        qr_image_url, qr_image_data = normalize_qr_image_value(
            str(bill.get('qr_image', factura.qr_image_url or '') or factura.qr_image_url or '')
        )
        safe_assign_charfield(factura, 'qr_image_url', qr_image_url)
        factura.qr_image_data = qr_image_data
        log_model_string_overflow_diagnostics(
            instance=factura, venta_id=factura.venta_id, factura_id=factura.pk, stage='emitir_factura_completa_sync'
        )
        factura.save(update_fields=['public_url', 'qr_data', 'qr_image_url', 'qr_image_data', 'updated_at'])
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

    # 3-5) Flujo híbrido: PDF carta personalizado + correo Factus.
    if not upload_custom_pdf_to_factus(factura):
        warnings.append({'component': 'pdf_factus', 'message': factura.ultimo_error_pdf or 'Error cargando PDF personalizado.'})
    if not send_invoice_email_via_factus(factura):
        email = str(factura.venta.cliente.email or '').strip()
        if email:
            warnings.append({'component': 'correo', 'message': factura.ultimo_error_correo or 'Error enviando correo por Factus.'})

    return {'factura': factura, 'warnings': warnings}
