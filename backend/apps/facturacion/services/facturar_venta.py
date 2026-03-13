"""Servicio de alto nivel para facturar una venta en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.facturacion.exceptions import FacturaDuplicadaError
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.consecutivo_service import get_next_invoice_number
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusValidationError
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.generate_qr_dian import generate_qr_dian
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def map_factus_status(response_json: dict[str, Any]) -> str:
    """Mapea estados de Factus a estados internos DIAN."""
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    status = str(bill.get('status', data.get('status', response_json.get('status', 'error')))).strip().lower()
    mapping = {
        'valid': 'ACEPTADA',
        'rejected': 'RECHAZADA',
        'pending': 'EN_PROCESO',
        'error': 'ERROR',
    }
    return mapping.get(status, 'ERROR')


def _extract_factus_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    return {
        'cufe': str(bill.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid', '')).strip(),
        'number': str(bill.get('number', '')).strip(),
        'xml_url': str(bill.get('xml_url', '')).strip(),
        'pdf_url': str(bill.get('pdf_url', '')).strip(),
        'status': map_factus_status(response_json),
    }


def facturar_venta(venta_id: int) -> FacturaElectronica:
    venta = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').get(pk=venta_id)
    if venta.tipo_comprobante != 'FACTURA':
        raise FactusValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
    if venta.estado != 'FACTURADA':
        raise FactusValidationError('La venta debe estar en estado FACTURADA antes de enviarse a Factus.')

    factura_existente = FacturaElectronica.objects.filter(venta=venta).first()
    if factura_existente:
        if not factura_existente.xml_local_path:
            download_xml(factura_existente)
        if not factura_existente.pdf_local_path:
            download_pdf(factura_existente)
        return factura_existente

    payload = build_invoice_payload(venta)
    numero = get_next_invoice_number()
    venta.numero_comprobante = numero
    venta.save(update_fields=['numero_comprobante', 'updated_at'])
    payload['number'] = numero
    payload['reference_code'] = numero
    reference_code = numero
    if FacturaElectronica.objects.filter(reference_code=reference_code).exists():
        raise FacturaDuplicadaError(f'Ya existe una factura electrónica con reference_code={reference_code}.')

    client = FactusClient()
    response_json = client.send_invoice(payload)

    fields = _extract_factus_data(response_json)
    required_fields = ['cufe', 'uuid', 'number', 'xml_url', 'pdf_url']
    missing_fields = [field for field in required_fields if not fields[field]]
    if missing_fields:
        logger.error('Respuesta incompleta Factus venta=%s faltantes=%s', venta.id, missing_fields)
        raise FactusAPIError('La respuesta de Factus no contiene todos los datos requeridos.')

    with transaction.atomic():
        factura, _ = FacturaElectronica.objects.update_or_create(
            venta=venta,
            defaults={
                **fields,
                'reference_code': reference_code,
                'codigo_error': response_json.get('error_code'),
                'mensaje_error': response_json.get('error_message'),
                'response_json': response_json,
            },
        )
        if factura.cufe:
            qr_file = generate_qr_dian(factura.number, factura.cufe)
            factura.qr.save(qr_file.name, qr_file, save=False)
            factura.save(update_fields=['qr', 'updated_at'])

    download_xml(factura)
    download_pdf(factura)
    return factura
