"""Servicio de alto nivel para facturar una venta en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusValidationError
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def _extract_factus_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    return {
        'cufe': str(bill.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid', '')).strip(),
        'number': str(bill.get('number', '')).strip(),
        'xml_url': str(bill.get('xml_url', '')).strip(),
        'pdf_url': str(bill.get('pdf_url', '')).strip(),
        'qr': str(bill.get('qr', '')).strip(),
        'status': str(bill.get('status', data.get('status', response_json.get('status', 'UNKNOWN')))).strip(),
    }


def facturar_venta(venta_id: int) -> FacturaElectronica:
    venta = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').get(pk=venta_id)
    if venta.tipo_comprobante != 'FACTURA':
        raise FactusValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
    if venta.estado != 'FACTURADA':
        raise FactusValidationError('La venta debe estar en estado FACTURADA antes de enviarse a Factus.')

    factura_existente = FacturaElectronica.objects.filter(venta=venta).first()
    if factura_existente:
        return factura_existente

    payload = build_invoice_payload(venta)
    client = FactusClient()
    response_json = client.send_invoice(payload)

    fields = _extract_factus_data(response_json)
    required_fields = ['cufe', 'uuid', 'number', 'xml_url', 'pdf_url', 'qr', 'status']
    missing_fields = [field for field in required_fields if not fields[field]]
    if missing_fields:
        logger.error('Respuesta incompleta Factus venta=%s faltantes=%s', venta.id, missing_fields)
        raise FactusAPIError('La respuesta de Factus no contiene todos los datos requeridos.')

    with transaction.atomic():
        factura, _ = FacturaElectronica.objects.update_or_create(
            venta=venta,
            defaults={
                **fields,
                'response_json': response_json,
            },
        )
    return factura
