"""Flujo híbrido: subir PDF Carta personalizado y enviar correo por Factus."""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient
from apps.facturacion.services.pdf_personalizado import build_pdf_personalizado_payload, generar_pdf_personalizado
from apps.facturacion.services.reconciliation import extract_factus_data

logger = logging.getLogger(__name__)


def upload_custom_pdf_to_factus(
    factura: FacturaElectronica,
    *,
    fallback_response_payload: dict | None = None,
) -> bool:
    """Sube el PDF Carta personalizado sin alterar estado electrónico de la factura."""
    if not factura.number and factura.pk:
        factura.refresh_from_db()
    if not factura.number and isinstance(fallback_response_payload, dict):
        extracted = extract_factus_data(fallback_response_payload)
        number = str(extracted.get('number') or '').strip()
        if number:
            factura.number = number
            if not factura.reference_code and extracted.get('reference_code'):
                factura.reference_code = str(extracted.get('reference_code') or '').strip()
            factura.save(update_fields=['number', 'reference_code', 'updated_at'])
    if not factura.number:
        factura.ultimo_error_pdf = 'Se pospone carga PDF: falta número oficial Factus persistido.'
        factura.save(update_fields=['ultimo_error_pdf', 'updated_at'])
        logger.warning('facturar_venta.pdf_personalizado_skip_missing_number factura_id=%s', factura.pk)
        return False

    try:
        generar_pdf_personalizado(factura)
        pdf_bytes, filename = build_pdf_personalizado_payload(factura)
        FactusClient().upload_custom_pdf(factura.number, pdf_bytes, filename=filename)
        factura.pdf_uploaded_to_factus = True
        factura.pdf_uploaded_at = timezone.now()
        factura.ultimo_error_pdf = ''
        factura.save(update_fields=['pdf_uploaded_to_factus', 'pdf_uploaded_at', 'ultimo_error_pdf', 'updated_at'])
        logger.info('facturar_venta.pdf_personalizado_subido factura_id=%s numero=%s', factura.pk, factura.number)
        return True
    except Exception as exc:
        factura.ultimo_error_pdf = str(exc)[:500]
        factura.save(update_fields=['ultimo_error_pdf', 'updated_at'])
        logger.warning(
            'facturar_venta.pdf_personalizado_error factura_id=%s numero=%s detail=%s',
            factura.pk,
            factura.number,
            factura.ultimo_error_pdf,
            exc_info=True,
        )
        return False


def send_invoice_email_via_factus(factura: FacturaElectronica) -> bool:
    """Envía correo por Factus si el cliente tiene email válido."""
    if not factura.number:
        return False
    email = str(getattr(factura.venta.cliente, 'email', '') or '').strip()
    if not email:
        return False

    try:
        FactusClient().send_invoice_email(factura.number, email=email)
        factura.correo_enviado = True
        factura.correo_enviado_at = timezone.now()
        factura.ultimo_error_correo = ''
        factura.save(update_fields=['correo_enviado', 'correo_enviado_at', 'ultimo_error_correo', 'updated_at'])
        logger.info('facturar_venta.correo_enviado_factus factura_id=%s numero=%s email=%s', factura.pk, factura.number, email)
        return True
    except (FactusAPIError, FactusAuthError, Exception) as exc:
        factura.ultimo_error_correo = str(exc)[:500]
        factura.save(update_fields=['ultimo_error_correo', 'updated_at'])
        logger.warning(
            'facturar_venta.correo_error factura_id=%s numero=%s email=%s detail=%s',
            factura.pk,
            factura.number,
            email,
            factura.ultimo_error_correo,
            exc_info=True,
        )
        return False
