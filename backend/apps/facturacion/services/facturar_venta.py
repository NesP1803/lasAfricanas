"""Servicio de alto nivel para facturar una venta en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.facturacion.exceptions import FacturaDuplicadaError
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.consecutivo_service import get_next_invoice_sequence, resolve_numbering_range
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient, FactusValidationError
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
    number = str(bill.get('number') or data.get('number', '')).strip()
    cufe = str(bill.get('cufe') or data.get('cufe', '')).strip()
    has_emission_identity = bool(number and cufe)
    if status == 'rejected':
        return 'RECHAZADA'
    if status == 'valid':
        return 'ACEPTADA'
    if has_emission_identity:
        # Factus puede reportar observaciones en bill.errors y aun así la factura existir.
        return 'ACEPTADA'
    if status == 'pending':
        return 'EN_PROCESO'
    return 'ERROR'


def _extract_bill_errors(response_json: dict[str, Any]) -> list[str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    errors = bill.get('errors', data.get('errors', []))
    if isinstance(errors, str):
        return [errors]
    if not isinstance(errors, list):
        return []
    normalized: list[str] = []
    for item in errors:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict):
            code = str(item.get('code', '')).strip()
            message = str(item.get('message', '')).strip()
            text = ' - '.join(part for part in [code, message] if part)
            if text:
                normalized.append(text)
    return normalized


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
        'qr_image': str(bill.get('qr_image', data.get('qr_image', ''))).strip(),
        'qr_url': str(bill.get('qr_url', data.get('qr_url', ''))).strip(),
        'public_url': str(bill.get('public_url', data.get('public_url', ''))).strip(),
        'zip_key': str(bill.get('zip_key', data.get('zip_key', ''))).strip(),
        'status': map_factus_status(response_json),
    }


def _merge_factus_fields(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    for key, value in extra.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


PERSISTABLE_FACTURA_FIELDS = {
    'cufe',
    'uuid',
    'number',
    'reference_code',
    'xml_url',
    'pdf_url',
    'status',
}


def _build_attempt_trace(
    *,
    factura: FacturaElectronica | None,
    payload: dict[str, Any],
    numero: str,
    reference_code: str,
    triggered_by: Usuario | None,
    status: str,
    response: dict[str, Any] | None = None,
    response_show: dict[str, Any] | None = None,
    response_download: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    final_fields: dict[str, Any] | None = None,
    bill_errors: list[str] | None = None,
) -> dict[str, Any]:
    previous = factura.response_json if factura and isinstance(factura.response_json, dict) else {}
    previous_attempts = previous.get('attempts', [])
    attempts = previous_attempts if isinstance(previous_attempts, list) else []
    attempts.append(
        {
            'status': status,
            'numero': numero,
            'reference_code': reference_code,
            'triggered_by_user_id': triggered_by.id if triggered_by else None,
            'error': error or {},
        }
    )
    return {
        'request': payload,
        'response': response,
        'response_show': response_show,
        'response_download': response_download,
        'final_fields': final_fields or {},
        'bill_errors': bill_errors or [],
        'venta_id': factura.venta_id if factura else None,
        'triggered_by_user_id': triggered_by.id if triggered_by else None,
        'attempts': attempts,
    }


def _persist_remote_error(
    *,
    factura: FacturaElectronica,
    payload: dict[str, Any],
    numero: str,
    reference_code: str,
    triggered_by: Usuario | None,
    stage: str,
    error: Exception,
) -> None:
    status_code = getattr(error, 'status_code', None)
    provider_detail = getattr(error, 'provider_detail', '')
    factura.status = 'ERROR'
    factura.codigo_error = str(status_code or error.__class__.__name__)
    factura.mensaje_error = provider_detail or str(error)
    factura.response_json = _build_attempt_trace(
        factura=factura,
        payload=payload,
        numero=numero,
        reference_code=reference_code,
        triggered_by=triggered_by,
        status='ERROR',
        error={
            'stage': stage,
            'error_type': error.__class__.__name__,
            'message': str(error),
            'status_code': status_code,
            'provider_detail': provider_detail,
        },
    )
    factura.save(update_fields=['status', 'codigo_error', 'mensaje_error', 'response_json', 'updated_at'])


def facturar_venta(venta_id: int, triggered_by: Usuario | None = None) -> FacturaElectronica:
    logger.info('facturar_venta.inicio venta_id=%s user_id=%s', venta_id, getattr(triggered_by, 'id', None))
    venta = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').get(pk=venta_id)
    if venta.tipo_comprobante != 'FACTURA':
        raise FactusValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
    if venta.estado == 'ANULADA':
        raise FactusValidationError('La venta está anulada y no se puede enviar a Factus.')
    if venta.estado not in {'COBRADA', 'FACTURADA'}:
        raise FactusValidationError('La venta debe estar en estado COBRADA antes de enviarse a Factus.')

    factura_existente = FacturaElectronica.objects.filter(venta=venta).first()
    if factura_existente and factura_existente.status == 'ACEPTADA':
        logger.info('facturar_venta.reutiliza_aceptada venta_id=%s factura=%s', venta.id, factura_existente.number)
        if not factura_existente.xml_local_path:
            download_xml(factura_existente)
        if not factura_existente.pdf_local_path:
            download_pdf(factura_existente)
        return factura_existente
    if factura_existente and factura_existente.status == 'EN_PROCESO':
        raise FactusValidationError('La factura electrónica está EN_PROCESO. No se permite reenviar todavía.')

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
    numero = str(venta.numero_comprobante or '').strip()
    if not numero:
        sequence = get_next_invoice_sequence()
        if not sequence.numbering_range_id:
            raise FactusValidationError(
                'Debe sincronizar/configurar el rango antes de facturar. Falta factus_range_id del rango seleccionado.'
            )
        numero = sequence.number
        payload['numbering_range_id'] = sequence.numbering_range_id
        venta.numero_comprobante = numero
        venta.save(update_fields=['numero_comprobante', 'updated_at'])
    elif not payload.get('numbering_range_id'):
        # Reintentos con número ya asignado: resolver rango sin incrementar consecutivo.
        rango = resolve_numbering_range(document_code='FACTURA_VENTA')
        if not rango.factus_range_id:
            raise FactusValidationError(
                'Debe sincronizar/configurar el rango antes de facturar. Falta factus_range_id del rango seleccionado.'
            )
        payload['numbering_range_id'] = int(rango.factus_range_id)

    payload['number'] = numero
    payload['reference_code'] = numero
    reference_code = numero
    if FacturaElectronica.objects.filter(reference_code=reference_code).exclude(venta=venta).exists():
        raise FacturaDuplicadaError(f'Ya existe una factura electrónica con reference_code={reference_code}.')

    factura, _ = FacturaElectronica.objects.update_or_create(
        venta=venta,
        defaults={
            'status': 'EN_PROCESO',
            'number': numero,
            'reference_code': reference_code,
            'response_json': _build_attempt_trace(
                factura=factura_existente,
                payload=payload,
                numero=numero,
                reference_code=reference_code,
                triggered_by=triggered_by,
                status='EN_PROCESO',
            ),
            'codigo_error': '',
            'mensaje_error': '',
        },
    )

    client = FactusClient()
    try:
        response_json = client.send_invoice(payload)
    except (FactusAPIError, FactusAuthError) as exc:
        _persist_remote_error(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            stage='send_invoice',
            error=exc,
        )
        logger.warning('facturar_venta.factus_rechazo venta_id=%s numero=%s', venta.id, numero)
        raise
    logger.info('facturar_venta.factus_response venta_id=%s keys=%s', venta.id, sorted(response_json.keys()))

    fields = _extract_factus_data(response_json)
    fields['number'] = fields.get('number') or numero
    fields['reference_code'] = fields.get('reference_code') or reference_code
    bill_errors = _extract_bill_errors(response_json)

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
        try:
            response_show_json = client.get_invoice(fields['number'])
        except (FactusAPIError, FactusAuthError) as exc:
            _persist_remote_error(
                factura=factura,
                payload=payload,
                numero=numero,
                reference_code=reference_code,
                triggered_by=triggered_by,
                stage='get_invoice',
                error=exc,
            )
            raise
        logger.info(
            'facturar_venta.factus_show_response venta_id=%s numero=%s keys=%s',
            venta.id,
            fields['number'],
            sorted(response_show_json.keys()),
        )
        fields = _merge_factus_fields(fields, _extract_factus_data(response_show_json))
        if not bill_errors:
            bill_errors = _extract_bill_errors(response_show_json)
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
                if not bill_errors:
                    bill_errors = _extract_bill_errors(response_download_json)
            except (FactusAPIError, FactusAuthError) as exc:
                _persist_remote_error(
                    factura=factura,
                    payload=payload,
                    numero=numero,
                    reference_code=reference_code,
                    triggered_by=triggered_by,
                    stage='get_invoice_downloads',
                    error=exc,
                )
                raise

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
        factura.status = 'ERROR'
        factura.codigo_error = 'RESPUESTA_INCOMPLETA'
        factura.mensaje_error = f'Factus no devolvió campos requeridos: {", ".join(missing_fields)}.'
        factura.response_json = _build_attempt_trace(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            status='ERROR',
            response=response_json,
            response_show=response_show_json,
            response_download=response_download_json,
            final_fields=fields,
            bill_errors=bill_errors,
            error={
                'message': 'Respuesta incompleta de Factus',
                'missing_fields': missing_fields,
            },
        )
        factura.save(update_fields=['status', 'codigo_error', 'mensaje_error', 'response_json', 'updated_at'])
        logger.error(
            'facturar_venta.respuesta_incompleta venta_id=%s numero=%s faltantes=%s',
            venta.id,
            fields.get('number') or numero,
            missing_fields,
        )
        raise FactusAPIError('La respuesta de Factus no contiene todos los datos requeridos.')

    persistable_fields = {k: v for k, v in fields.items() if k in PERSISTABLE_FACTURA_FIELDS}

    with transaction.atomic():
        factura = FacturaElectronica.objects.select_for_update().get(pk=factura.pk)
        for key, value in persistable_fields.items():
            setattr(factura, key, value)
        factura.reference_code = persistable_fields.get('reference_code') or reference_code
        factura.codigo_error = (
            'OBSERVACIONES_FACTUS'
            if bill_errors and persistable_fields.get('status') == 'ACEPTADA'
            else response_json.get('error_code')
        )
        factura.mensaje_error = (
            '; '.join(bill_errors)
            if bill_errors
            else response_json.get('error_message')
        )
        factura.response_json = _build_attempt_trace(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            status=persistable_fields.get('status', 'ERROR'),
            response=response_json,
            response_show=response_show_json,
            response_download=response_download_json,
            final_fields={**fields, 'persisted_fields': persistable_fields},
            bill_errors=bill_errors,
        )
        factura.save()

        venta.factura_electronica_uuid = fields.get('uuid') or ''
        venta.factura_electronica_cufe = fields.get('cufe') or ''
        venta.fecha_envio_dian = factura.updated_at
        venta.save(update_fields=['factura_electronica_uuid', 'factura_electronica_cufe', 'fecha_envio_dian', 'updated_at'])
        logger.info(
            'facturar_venta.persistida venta_id=%s factura=%s status=%s reference_code=%s',
            venta.id,
            factura.number,
            factura.status,
            factura.reference_code,
        )
        if factura.cufe and factura.number:
            qr_file = generate_qr_dian(factura.number, factura.cufe)
            factura.qr.save(qr_file.name, qr_file, save=False)
            factura.save(update_fields=['qr', 'updated_at'])

    try:
        if factura.xml_url:
            download_xml(factura)
    except DescargaFacturaError:
        logger.warning('facturar_venta.xml_descarga_error venta_id=%s factura=%s', venta.id, factura.number, exc_info=True)
    try:
        if factura.pdf_url:
            download_pdf(factura)
    except DescargaFacturaError:
        logger.warning('facturar_venta.pdf_descarga_error venta_id=%s factura=%s', venta.id, factura.number, exc_info=True)
    logger.info('facturar_venta.fin_ok venta_id=%s factura=%s', venta.id, factura.number)
    return factura
