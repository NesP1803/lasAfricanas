"""Servicio para consultar y sincronizar el estado DIAN de una factura en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.exceptions import FacturaNoEncontrada, FactusConsultaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient

logger = logging.getLogger(__name__)


def map_factus_status(status: str | None) -> str:
    """Mapea estados de Factus a estados internos."""
    normalized = (status or '').strip().lower()
    mapping = {
        'valid': 'ACEPTADA_DIAN',
        'rejected': 'RECHAZADA_DIAN',
        'pending': 'PENDIENTE',
    }
    return mapping.get(normalized, 'PENDIENTE')


def _extract_bill_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    status = bill.get('status', data.get('status', response_json.get('status')))
    return {
        'cufe': str(bill.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid', '')).strip(),
        'status': map_factus_status(str(status) if status is not None else None),
        'xml_url': str(bill.get('xml_url', '')).strip(),
        'pdf_url': str(bill.get('pdf_url', '')).strip(),
        'qr': str(bill.get('qr', '')).strip(),
    }


def sync_invoice_status(numero_factura: str) -> FacturaElectronica:
    logger.info('consulta_factura numero=%s', numero_factura)

    factura = FacturaElectronica.objects.filter(number=numero_factura).first()
    if factura is None:
        logger.warning('error_consulta_factura numero=%s detalle=factura_no_encontrada', numero_factura)
        raise FacturaNoEncontrada(f'No existe factura con número {numero_factura}.')

    client = FactusClient()
    try:
        response_json = client.get_invoice(numero_factura)
    except (FactusAPIError, FactusAuthError) as exc:
        logger.exception('error_consulta_factura numero=%s', numero_factura)
        raise FactusConsultaError('No fue posible consultar el estado de la factura en Factus.') from exc

    payload = _extract_bill_data(response_json)

    with transaction.atomic():
        factura.cufe = payload['cufe'] or factura.cufe
        factura.uuid = payload['uuid'] or factura.uuid
        factura.status = payload['status']
        factura.xml_url = payload['xml_url'] or factura.xml_url
        factura.pdf_url = payload['pdf_url'] or factura.pdf_url
        factura.qr = payload['qr'] or factura.qr
        factura.response_json = response_json
        factura.save(
            update_fields=[
                'cufe',
                'uuid',
                'status',
                'xml_url',
                'pdf_url',
                'qr',
                'response_json',
                'updated_at',
            ]
        )

    logger.info('sincronizacion_estado numero=%s estado=%s', factura.number, factura.status)
    return factura
