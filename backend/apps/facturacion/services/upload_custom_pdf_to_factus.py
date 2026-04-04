"""Flujo híbrido: subir PDF Carta personalizado y enviar correo por Factus."""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient
from apps.facturacion.services.pdf_personalizado import build_pdf_personalizado_payload, generar_pdf_personalizado

logger = logging.getLogger(__name__)


def upload_custom_pdf_to_factus(factura: FacturaElectronica) -> bool:
    """Sube el PDF Carta personalizado sin alterar estado electrónico de la factura."""
    if not factura.number:
        raise ValueError('La factura no tiene number confirmado para subir PDF personalizado.')

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
