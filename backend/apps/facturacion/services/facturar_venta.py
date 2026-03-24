"""Servicio de alto nivel para facturar una venta en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.facturacion.exceptions import FacturaDuplicadaError
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.consecutivo_service import get_next_invoice_sequence
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusValidationError
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.generate_qr_dian import generate_qr_dian
from apps.usuarios.models import Usuario
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
    document = bill.get('document', {}) if isinstance(bill.get('document', {}), dict) else {}
    file_data = bill.get('files', {}) if isinstance(bill.get('files', {}), dict) else {}
    return {
        'cufe': str(bill.get('cufe') or document.get('cufe') or data.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid') or document.get('uuid') or data.get('uuid', '')).strip(),
        'number': str(bill.get('number') or document.get('number') or data.get('number', '')).strip(),
        'reference_code': str(
            bill.get('reference_code') or document.get('reference_code') or data.get('reference_code', '')
        ).strip(),
        'xml_url': str(
            bill.get('xml_url') or file_data.get('xml_url') or document.get('xml_url') or data.get('xml_url', '')
        ).strip(),
        'pdf_url': str(
            bill.get('pdf_url') or file_data.get('pdf_url') or document.get('pdf_url') or data.get('pdf_url', '')
        ).strip(),
        'qr': str(bill.get('qr', data.get('qr', ''))).strip(),
        'qr_url': str(bill.get('qr_url', data.get('qr_url', ''))).strip(),
        'zip_key': str(bill.get('zip_key', data.get('zip_key', ''))).strip(),
        'status': map_factus_status(response_json),
    }


def _merge_factus_fields(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    for key, value in extra.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def facturar_venta(venta_id: int, triggered_by: Usuario | None = None) -> FacturaElectronica:
    logger.info('facturar_venta.inicio venta_id=%s user_id=%s', venta_id, getattr(triggered_by, 'id', None))
    venta = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').get(pk=venta_id)
    if venta.tipo_comprobante != 'FACTURA':
        raise FactusValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
    if venta.estado != 'FACTURADA':
        raise FactusValidationError('La venta debe estar en estado FACTURADA antes de enviarse a Factus.')

    factura_existente = FacturaElectronica.objects.filter(venta=venta).first()
    if factura_existente:
        logger.info('facturar_venta.reutiliza_existente venta_id=%s factura=%s', venta.id, factura_existente.number)
        if not factura_existente.xml_local_path:
            download_xml(factura_existente)
        if not factura_existente.pdf_local_path:
            download_pdf(factura_existente)
        return factura_existente

    payload = build_invoice_payload(venta)
    logger.info(
        'facturar_venta.payload venta_id=%s items=%s customer=%s numbering_range_id=%s '
        'customer_tribute_id=%s first_discount_rate=%s first_is_excluded=%s send_email=%s',
        venta.id,
        len(payload.get('items', [])),
        payload.get('customer', {}).get('identification'),
        payload.get('numbering_range_id'),
        payload.get('customer', {}).get('tribute_id'),
        (payload.get('items', [{}])[0].get('discount_rate') if payload.get('items') else None),
        (payload.get('items', [{}])[0].get('is_excluded') if payload.get('items') else None),
        payload.get('send_email'),
    )
    sequence = get_next_invoice_sequence()
    if not sequence.numbering_range_id:
        raise FactusValidationError(
            'Debe sincronizar/configurar el rango antes de facturar. Falta factus_range_id del rango seleccionado.'
        )
    numero = sequence.number
    venta.numero_comprobante = numero
    venta.save(update_fields=['numero_comprobante', 'updated_at'])
    payload['numbering_range_id'] = sequence.numbering_range_id
    payload['number'] = numero
    payload['reference_code'] = numero
    reference_code = numero
    if FacturaElectronica.objects.filter(reference_code=reference_code).exists():
        raise FacturaDuplicadaError(f'Ya existe una factura electrónica con reference_code={reference_code}.')

    client = FactusClient()
    try:
        response_json = client.send_invoice(payload)
    except FactusAPIError:
        logger.warning('facturar_venta.factus_rechazo venta_id=%s numero=%s', venta.id, numero)
        raise
    logger.info('facturar_venta.factus_response venta_id=%s keys=%s', venta.id, sorted(response_json.keys()))

    fields = _extract_factus_data(response_json)
    fields['number'] = fields.get('number') or numero
    fields['reference_code'] = fields.get('reference_code') or reference_code

    missing_before = [field for field in ['uuid', 'xml_url', 'pdf_url'] if not fields.get(field)]
    response_show_json: dict[str, Any] | None = None
    response_download_json: dict[str, Any] | None = None
    if missing_before:
        logger.info(
            'facturar_venta.factus_complemento_inicio venta_id=%s numero=%s faltantes=%s',
            venta.id,
            fields['number'],
            missing_before,
        )
        response_show_json = client.get_invoice(fields['number'])
        logger.info(
            'facturar_venta.factus_show_response venta_id=%s numero=%s keys=%s',
            venta.id,
            fields['number'],
            sorted(response_show_json.keys()),
        )
        fields = _merge_factus_fields(fields, _extract_factus_data(response_show_json))
        missing_after_show = [field for field in ['uuid', 'xml_url', 'pdf_url'] if not fields.get(field)]
        if missing_after_show:
            try:
                response_download_json = client.get_invoice_downloads(fields['number'])
                logger.info(
                    'facturar_venta.factus_download_response venta_id=%s numero=%s keys=%s',
                    venta.id,
                    fields['number'],
                    sorted(response_download_json.keys()),
                )
                fields = _merge_factus_fields(fields, _extract_factus_data(response_download_json))
            except FactusAPIError:
                logger.warning(
                    'facturar_venta.factus_download_error venta_id=%s numero=%s',
                    venta.id,
                    fields['number'],
                    exc_info=True,
                )

    # Factus puede no devolver uuid/xml/pdf en validate; se completa con show/download
    # y, como último recurso, se genera URL directa de descarga para no abortar el flujo.
    if not fields.get('uuid'):
        fields['uuid'] = fields.get('cufe') or fields.get('reference_code') or fields['number']
    if not fields.get('xml_url'):
        fields['xml_url'] = f'{client.base_url}/v1/bills/download-xml/{fields["number"]}'
    if not fields.get('pdf_url'):
        fields['pdf_url'] = f'{client.base_url}/v1/bills/download-pdf/{fields["number"]}'

    required_fields = ['cufe', 'number', 'uuid', 'xml_url', 'pdf_url']
    missing_fields = [field for field in required_fields if not fields[field]]
    if missing_fields:
        logger.error(
            'facturar_venta.respuesta_incompleta venta_id=%s numero=%s faltantes=%s',
            venta.id,
            fields.get('number') or numero,
            missing_fields,
        )
        raise FactusAPIError('La respuesta de Factus no contiene todos los datos requeridos.')

    with transaction.atomic():
        factura, _ = FacturaElectronica.objects.update_or_create(
            venta=venta,
            defaults={
                **fields,
                'reference_code': fields.get('reference_code') or reference_code,
                'codigo_error': response_json.get('error_code'),
                'mensaje_error': response_json.get('error_message'),
                'response_json': {
                    'request': payload,
                    'response': response_json,
                    'response_show': response_show_json,
                    'response_download': response_download_json,
                    'final_fields': fields,
                    'venta_id': venta.id,
                    'triggered_by_user_id': triggered_by.id if triggered_by else None,
                },
            },
        )
        venta.factura_electronica_uuid = fields['uuid']
        venta.factura_electronica_cufe = fields['cufe']
        venta.fecha_envio_dian = factura.created_at
        venta.save(update_fields=['factura_electronica_uuid', 'factura_electronica_cufe', 'fecha_envio_dian', 'updated_at'])
        logger.info(
            'facturar_venta.persistida venta_id=%s factura=%s status=%s reference_code=%s',
            venta.id,
            factura.number,
            factura.status,
            factura.reference_code,
        )
        if factura.cufe:
            qr_file = generate_qr_dian(factura.number, factura.cufe)
            factura.qr.save(qr_file.name, qr_file, save=False)
            factura.save(update_fields=['qr', 'updated_at'])

    try:
        download_xml(factura)
    except DescargaFacturaError:
        logger.warning('facturar_venta.xml_descarga_error venta_id=%s factura=%s', venta.id, factura.number, exc_info=True)
    try:
        download_pdf(factura)
    except DescargaFacturaError:
        logger.warning('facturar_venta.pdf_descarga_error venta_id=%s factura=%s', venta.id, factura.number, exc_info=True)
    logger.info('facturar_venta.fin_ok venta_id=%s factura=%s', venta.id, factura.number)
    return factura
