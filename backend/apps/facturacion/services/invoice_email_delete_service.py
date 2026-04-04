"""Operaciones explícitas de correo/eliminación para facturas Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.download_invoice_files import decode_base64_to_bytes, persist_file_bytes
from apps.facturacion.services.factus_client import FactusClient, FactusValidationError

logger = logging.getLogger(__name__)


def get_invoice_email_content(*, factura: FacturaElectronica, save_zip: bool = False) -> dict[str, Any]:
    if not factura.number:
        raise FactusValidationError('Factura sin número electrónico aún.')

    payload = FactusClient().get_invoice_email_content(factura.number)
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return payload

    if save_zip:
        encoded_zip = str(data.get('zip_base_64_encoded') or '').strip()
        if encoded_zip:
            zip_bytes = decode_base64_to_bytes(encoded_zip, document_type='ZIP-CORREO')
            zip_name = str(data.get('file_name') or f'{factura.number}.zip').strip()
            data['zip_local_path'] = persist_file_bytes(folder='correo', filename=zip_name, content=zip_bytes)
            payload['data'] = data
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

    payload = FactusClient().send_invoice_email(
        factura.number,
        email=resolved_email,
        pdf_base_64_encoded=pdf_base_64_encoded,
    )
    factura.correo_enviado = True
    factura.correo_enviado_at = timezone.now()
    factura.ultimo_error_correo = ''
    factura.save(update_fields=['correo_enviado', 'correo_enviado_at', 'ultimo_error_correo', 'updated_at'])
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
