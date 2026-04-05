"""Operaciones explícitas de correo/eliminación para facturas Factus."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.factura_assets_service import store_factura_email_zip
from apps.facturacion.services.factus_client import FactusClient, FactusValidationError

logger = logging.getLogger(__name__)


def get_invoice_email_content(*, factura: FacturaElectronica, save_zip: bool = False) -> dict[str, Any]:
    if not factura.number:
        raise FactusValidationError('Factura sin número electrónico aún.')

    payload = FactusClient().get_invoice_email_content(factura.number)
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return payload

    if data.get('subject'):
        factura.email_subject = str(data.get('subject') or '').strip()

    if save_zip:
        if data.get('zip_base_64_encoded'):
            data['zip_local_path'] = store_factura_email_zip(factura, payload)
            payload['data'] = data
    factura.save(update_fields=['email_subject', 'email_zip_local_path', 'updated_at'])
    return payload


def send_invoice_email(
    *,
    factura: FacturaElectronica,
    email: str | None = None,
    pdf_base_64_encoded: str | None = None,
) -> dict[str, Any]:
    if not factura.number:
        raise FactusValidationError('Factura sin número electrónico aún.')
    resolved_email = str(email or getattr(factura.venta.cliente, 'email', '') or '').strip()
    if not resolved_email:
        raise FactusValidationError('El adquiriente no tiene correo configurado para envío por Factus.')

    if pdf_base_64_encoded is None and factura.pdf_local_path:
        try:
            pdf_path = Path(settings.MEDIA_ROOT) / str(factura.pdf_local_path)
            with pdf_path.open('rb') as file_handler:
                pdf_base_64_encoded = base64.b64encode(file_handler.read()).decode('utf-8')
        except Exception:
            pdf_base_64_encoded = None

    payload = FactusClient().send_invoice_email(
        factura.number,
        email=resolved_email,
        pdf_base_64_encoded=pdf_base_64_encoded,
    )
    factura.correo_enviado = True
    factura.correo_enviado_at = timezone.now()
    factura.email_sent_at = factura.correo_enviado_at
    factura.ultimo_error_correo = ''
    factura.email_last_error = ''
    factura.response_json = {
        **(factura.response_json or {}),
        'send_email_response': payload,
    }
    factura.save(
        update_fields=[
            'correo_enviado',
            'correo_enviado_at',
            'email_sent_at',
            'ultimo_error_correo',
            'email_last_error',
            'response_json',
            'updated_at',
        ]
    )
    logger.info(
        'factura_email.ok factura_id=%s number=%s custom_pdf=%s',
        factura.id,
        factura.number,
        bool(pdf_base_64_encoded),
    )
    return payload


def delete_invoice_in_factus(*, factura: FacturaElectronica) -> dict[str, Any]:
    if not factura.number:
        raise FactusValidationError('Factura sin número electrónico aún.')
    if not factura.reference_code:
        raise FactusValidationError('Factura sin reference_code; no se puede eliminar en Factus.')
    if (factura.estado_electronico or factura.status) in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
        raise FactusValidationError('No se puede eliminar una factura ya validada/aceptada por DIAN.')

    payload = FactusClient().delete_invoice(factura.reference_code)
    factura.status = 'RECHAZADA'
    factura.estado_electronico = 'RECHAZADA'
    factura.mensaje_error = 'Documento eliminado/cancelado en Factus por acción administrativa.'
    factura.save(update_fields=['status', 'estado_electronico', 'mensaje_error', 'updated_at'])
    logger.info('factura_delete.ok factura_id=%s number=%s reference_code=%s', factura.id, factura.number, factura.reference_code)
    return payload
