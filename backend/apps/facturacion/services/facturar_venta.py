"""Servicio de alto nivel para facturar una venta en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import DataError, transaction
from django.utils import timezone

from apps.facturacion.exceptions import FacturaDuplicadaError, FacturaPersistenciaError
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.consecutivo_service import get_next_invoice_sequence, resolve_numbering_range
from apps.facturacion.services.document_fetcher import sync_existing_pending_invoice
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.electronic_state_machine import (
    extract_bill_errors as _extract_bill_errors,
    map_factus_status,
)
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factura_assets_service import sync_invoice_assets
from apps.facturacion.services.factus_client import (
    FactusAPIError,
    FactusAuthError,
    FactusClient,
    FactusPendingDianError,
    FactusValidationError,
)
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.generate_qr_dian import generate_qr_dian
from apps.facturacion.services.persistence import (
    assign_qr_image_fields,
    build_attempt_trace,
    persist_local_validation_error,
    persist_pending_dian_conflict,
    persist_remote_error,
)
from apps.facturacion.services.persistence_safety import (
    log_model_string_overflow_diagnostics,
    safe_assign_charfield,
    safe_assign_json,
)
from apps.facturacion.services.reconciliation import (
    PERSISTABLE_FACTURA_FIELDS,
    assert_emitted_document_matches_sale,
    extract_factus_data,
    merge_factus_fields,
)
from apps.facturacion.services.reference_code import resolve_reference_code, generate_unique_reference_code
from apps.facturacion.services.totals import (
    DOCUMENT_CONCILIATION_ERROR_CODE,
    assert_document_conciliation,
    sync_sale_totals_before_emit,
)
from apps.facturacion.services.result_types import FacturacionContext
from apps.facturacion.services.upload_custom_pdf_to_factus import (
    send_invoice_email_via_factus,
    upload_custom_pdf_to_factus,
)
from apps.facturacion.services.validators import (
    has_definitive_electronic_identifiers,
    number_matches_active_range,
    validate_customer_for_factus,
    validate_payload_tax_consistency,
)
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)
FINAL_ACCEPTED_STATUSES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}


def _assert_document_conciliation(*, venta: Venta, request_payload: dict[str, Any], response_payload: dict[str, Any], logger_context: dict[str, Any]) -> None:
    return assert_document_conciliation(
        venta=venta,
        request_payload=request_payload,
        response_payload=response_payload,
        logger_context=logger_context,
    )


def _generate_unique_reference_code(venta_id: int, numero: str | None = None) -> str:
    return generate_unique_reference_code(venta_id, numero)


def _resolve_reference_code(*, venta: Venta, factura_existente: FacturaElectronica | None, numero: str) -> str:
    return resolve_reference_code(venta=venta, factura_existente=factura_existente, numero=numero)


def _build_and_log_factus_payload(venta: Venta) -> dict[str, Any]:
    payload = build_invoice_payload(venta)
    customer = payload.get('customer', {}) if isinstance(payload.get('customer'), dict) else {}
    items = payload.get('items', []) if isinstance(payload.get('items'), list) else []
    first_item = items[0] if items and isinstance(items[0], dict) else {}
    logger.info('facturar_venta.payload_normalizado venta_id=%s payload=%s', venta.id, payload)
    logger.info(
        'facturar_venta.payload_componentes venta_id=%s customer=%s payment_form=%s payment_method=%s '
        'numbering_range_id=%s operation_type=%s first_item=%s items_count=%s',
        venta.id,
        customer,
        payload.get('payment_form'),
        payload.get('payment_method_code'),
        payload.get('numbering_range_id'),
        payload.get('operation_type'),
        first_item,
        len(items),
    )
    return payload


def _number_matches_active_range(numero: str, prefijo_rango: str) -> bool:
    numero_normalizado = str(numero or '').strip().upper()
    prefijo_normalizado = str(prefijo_rango or '').strip().upper()
    if not numero_normalizado or not prefijo_normalizado:
        return False
    return numero_normalizado.startswith(prefijo_normalizado)


def _generate_unique_reference_code(venta_id: int, numero: str | None = None) -> str:
    ts = timezone.now().strftime('%Y%m%d%H%M%S')
    short = uuid.uuid4().hex[:8].upper()
    if numero:
        return f'{numero}-{ts}-{short}'
    return f'VENTA-{venta_id}-{ts}-{short}'


def _resolve_reference_code(
    *,
    venta: Venta,
    factura_existente: FacturaElectronica | None,
    numero: str,
) -> str:
    if factura_existente and str(factura_existente.reference_code or '').strip():
        return str(factura_existente.reference_code).strip()
    return _generate_unique_reference_code(venta.id, numero)


def _has_definitive_electronic_identifiers(factura: FacturaElectronica | None) -> bool:
    if factura is None:
        return False
    return bool(
        str(factura.uuid or '').strip()
        and str(factura.cufe or '').strip()
        and str(factura.number or '').strip()
    )


def _persist_local_validation_error(
    *,
    factura: FacturaElectronica,
    payload: dict[str, Any],
    numero: str,
    reference_code: str,
    triggered_by: Usuario | None,
    error: Exception,
    response: dict[str, Any] | None = None,
    response_show: dict[str, Any] | None = None,
    response_download: dict[str, Any] | None = None,
) -> None:
    if factura.estado_electronico == 'ACEPTADA' and factura.cufe:
        logger.error(
            'facturar_venta.local_validation_conflict_ignored venta_id=%s factura_id=%s numero=%s',
            factura.venta_id,
            factura.pk,
            factura.number,
        )
        return

    factura.estado_electronico = 'RECHAZADA'
    error_text = str(error)
    if DOCUMENT_CONCILIATION_ERROR_CODE in error_text:
        factura.codigo_error = DOCUMENT_CONCILIATION_ERROR_CODE
    elif 'devolvió number=' in error_text:
        factura.codigo_error = MISMATCH_ERROR_CODE
    else:
        factura.codigo_error = LOCAL_VALIDATION_ERROR_CODE
    factura.mensaje_error = error_text
    factura.response_json = _build_attempt_trace(
        factura=factura,
        payload=payload,
        numero=numero,
        reference_code=reference_code,
        triggered_by=triggered_by,
        status='RECHAZADA',
        response=response,
        response_show=response_show,
        response_download=response_download,
        error={
            'stage': 'local_document_validation',
            'error_type': error.__class__.__name__,
            'message': error_text,
            'technical_status': LOCAL_VALIDATION_ERROR_CODE,
        },
    )
    metadata = _retry_metadata(factura, pending=False)
    factura.retry_count = metadata['retry_count']
    factura.last_retry_at = metadata['last_retry_at']
    factura.next_retry_at = metadata['next_retry_at']
    factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])


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
    is_validation_error = isinstance(error, FactusAPIError) and getattr(error, 'status_code', 0) in {400, 401, 403, 404, 409, 422}
    factura.estado_electronico = 'RECHAZADA' if is_validation_error else 'ERROR_INTEGRACION'
    safe_assign_charfield(factura, 'codigo_error', str(status_code or error.__class__.__name__))
    factura.mensaje_error = provider_detail or str(error)
    safe_assign_json(
        factura,
        'response_json',
        _build_attempt_trace(
        factura=factura,
        payload=payload,
        numero=numero,
        reference_code=reference_code,
        triggered_by=triggered_by,
        status=factura.estado_electronico,
        error={
            'stage': stage,
            'error_type': error.__class__.__name__,
            'message': str(error),
            'status_code': status_code,
            'provider_detail': provider_detail,
        },
        ),
    )
    metadata = _retry_metadata(factura, pending=not is_validation_error)
    factura.retry_count = metadata['retry_count']
    factura.last_retry_at = metadata['last_retry_at']
    factura.next_retry_at = metadata['next_retry_at']
    log_model_string_overflow_diagnostics(
        instance=factura, venta_id=factura.venta_id, factura_id=factura.pk, stage='persist_remote_error'
    )
    factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])


def _persist_pending_dian_conflict(
    *,
    factura: FacturaElectronica,
    payload: dict[str, Any],
    numero: str,
    reference_code: str,
    triggered_by: Usuario | None,
    error: FactusPendingDianError,
) -> None:
    provider_payload = error.provider_payload if isinstance(error.provider_payload, dict) else {}
    message = str(provider_payload.get('message') or error.provider_detail or str(error))
    factura.estado_electronico = 'PENDIENTE_REINTENTO'
    safe_assign_charfield(factura, 'codigo_error', 'FACTUS_PENDING_DIAN_409')
    factura.mensaje_error = message
    safe_assign_json(
        factura,
        'response_json',
        _build_attempt_trace(
        factura=factura,
        payload=payload,
        numero=numero,
        reference_code=reference_code,
        triggered_by=triggered_by,
        status='PENDIENTE_REINTENTO',
        error={
            'stage': 'send_invoice',
            'error_type': error.__class__.__name__,
            'message': str(error),
            'status_code': error.status_code,
            'provider_detail': error.provider_detail,
            'provider_payload': provider_payload,
            'semantic_status': 'PENDIENTE_DIAN',
        },
        ),
    )
    metadata = _retry_metadata(factura, pending=True)
    factura.retry_count = metadata['retry_count']
    factura.last_retry_at = metadata['last_retry_at']
    factura.next_retry_at = metadata['next_retry_at']
    log_model_string_overflow_diagnostics(
        instance=factura, venta_id=factura.venta_id, factura_id=factura.pk, stage='persist_pending_dian_conflict'
    )
    factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])


def _sync_existing_pending_invoice(
    *,
    factura: FacturaElectronica,
    venta: Venta,
    triggered_by: Usuario | None,
) -> FacturaElectronica:
    """Intenta sincronizar una factura EN_PROCESO existente sin reenviar."""
    if not factura.number:
        return factura
    client = FactusClient()
    try:
        response = client.get_invoice(factura.number)
    except (FactusAPIError, FactusAuthError):
        logger.info(
            'facturar_venta.pending_sync_no_disponible venta_id=%s numero=%s',
            venta.id,
            factura.number,
        )
        return factura

    fields = _extract_factus_data(response)
    _assert_emitted_document_matches_sale(
        venta=venta,
        fields=fields,
        expected_number=factura.number or str(venta.numero_comprobante or ''),
        expected_reference_code=factura.reference_code or str(venta.numero_comprobante or ''),
    )
    bill_errors = _extract_bill_errors(response)
    missing_after_show = [field for field in ['xml_url', 'pdf_url'] if not fields.get(field)]
    if missing_after_show:
        try:
            response_download = client.get_invoice_downloads(factura.number)
            fields = _merge_factus_fields(fields, _extract_factus_data(response_download))
            _assert_emitted_document_matches_sale(
                venta=venta,
                fields=fields,
                expected_number=factura.number or str(venta.numero_comprobante or ''),
                expected_reference_code=factura.reference_code or str(venta.numero_comprobante or ''),
            )
            if not bill_errors:
                bill_errors = _extract_bill_errors(response_download)
        except (FactusAPIError, FactusAuthError):
            logger.info(
                'facturar_venta.pending_sync_download_no_disponible venta_id=%s numero=%s',
                venta.id,
                factura.number,
            )
    persistable_fields = {k: v for k, v in fields.items() if k in PERSISTABLE_FACTURA_FIELDS}
    with transaction.atomic():
        locked = FacturaElectronica.objects.select_for_update().get(pk=factura.pk)
        for key, value in persistable_fields.items():
            if value:
                if key == 'qr':
                    locked.qr_data = value
                elif key == 'qr_image':
                    _assign_qr_image_fields(locked, value)
                else:
                    setattr(locked, key, value)
        locked.estado_electronico = locked.estado_electronico or 'PENDIENTE_REINTENTO'
        locked.emitida_en_factus = bool(locked.number and locked.cufe)
        locked.codigo_error = response.get('error_code') or locked.codigo_error
        locked.mensaje_error = '; '.join(bill_errors) if bill_errors else (response.get('error_message') or locked.mensaje_error)
        locked.response_json = _build_attempt_trace(
            factura=locked,
            payload={},
            numero=locked.number or factura.number,
            reference_code=locked.reference_code or factura.reference_code or '',
            triggered_by=triggered_by,
            status=locked.estado_electronico,
            response=response,
            final_fields={**fields, 'persisted_fields': persistable_fields, 'source': 'get_invoice_on_pending'},
            bill_errors=bill_errors,
        )
        log_model_string_overflow_diagnostics(
            instance=locked, venta_id=venta.id, factura_id=locked.pk, stage='sync_existing_pending_invoice'
        )
        locked.save(update_fields=['estado_electronico', 'cufe', 'uuid', 'number', 'reference_code', 'xml_url', 'pdf_url', 'public_url', 'qr_data', 'qr_image_url', 'qr_image_data', 'codigo_error', 'mensaje_error', 'response_json', 'updated_at'])
        logger.info(
            'facturar_venta.pending_sync_result venta_id=%s numero=%s status=%s',
            venta.id,
            locked.number,
            locked.estado_electronico,
        )
        if locked.estado_electronico == 'ACEPTADA' and locked.cufe and locked.number and not locked.qr:
            qr_file = generate_qr_dian(locked.number, locked.cufe)
            locked.qr.save(qr_file.name, qr_file, save=False)
            locked.save(update_fields=['qr', 'updated_at'])
        try:
            if locked.xml_url:
                download_xml(locked)
        except DescargaFacturaError:
            logger.warning(
                'facturar_venta.pending_sync_xml_descarga_error venta_id=%s factura=%s',
                venta.id,
                locked.number,
                exc_info=True,
            )
        try:
            if locked.pdf_url:
                download_pdf(locked)
        except DescargaFacturaError:
            logger.warning(
                'facturar_venta.pending_sync_pdf_descarga_error venta_id=%s factura=%s',
                venta.id,
                locked.number,
                exc_info=True,
            )
        return locked


def _validate_customer_for_factus(customer: dict[str, Any], venta: Venta) -> None:
    identification = str(customer.get('identification') or '').strip()
    names = str(customer.get('names') or '').strip()
    identification_document_id = customer.get('identification_document_id')
    missing_fields: list[str] = []
    if not identification:
        missing_fields.append('identification')
    if not names:
        missing_fields.append('names')
    if not identification_document_id:
        missing_fields.append('identification_document_id')
    if missing_fields:
        logger.warning(
            'facturar_venta.customer_incompleto venta_id=%s cliente_id=%s faltantes=%s customer=%s',
            venta.id,
            venta.cliente_id,
            missing_fields,
            {
                'identification': identification,
                'names': names,
                'identification_document_id': identification_document_id,
                'tribute_id': customer.get('tribute_id'),
            },
        )
        field_messages = {
            'identification': 'El cliente seleccionado no tiene número de identificación configurado para facturación electrónica.',
            'names': 'El cliente seleccionado no tiene nombre o razón social configurado para facturación electrónica.',
            'identification_document_id': 'El cliente seleccionado no tiene tipo de documento homologado para Factus.',
        }
        raise FactusValidationError(field_messages[missing_fields[0]])


def _validate_payload_tax_consistency(payload: dict[str, Any], venta: Venta) -> None:
    customer = payload.get('customer', {}) if isinstance(payload.get('customer'), dict) else {}
    items = payload.get('items', []) if isinstance(payload.get('items'), list) else []
    if not items:
        raise FactusValidationError('La factura no tiene ítems para emitir en Factus.')
    if not payload.get('operation_type'):
        raise FactusValidationError('Falta operation_type en el payload Factus.')
    if not payload.get('payment_form') or not payload.get('payment_method_code'):
        raise FactusValidationError('Falta payment_form/payment_method_code en el payload Factus.')

    taxable_count = 0
    excluded_tribute_id = int(get_tribute_id('NO_CAUSA', default=1))
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        is_excluded = _to_bool(item.get('is_excluded'))
        tax_rate = _to_decimal_or_none(item.get('tax_rate')) or Decimal('0.00')
        taxable_amount = _to_decimal_or_none(item.get('taxable_amount')) or Decimal('0.00')
        tax_amount = _to_decimal_or_none(item.get('tax_amount')) or Decimal('0.00')
        tribute_id = item.get('tribute_id')
        if is_excluded and tax_rate > Decimal('0.00'):
            raise FactusValidationError(
                f'Ítem excluido inválido en línea {index}: tax_rate debe ser 0 cuando is_excluded=1.'
            )
        if not is_excluded and tax_rate <= Decimal('0.00'):
            raise FactusValidationError(
                f'Ítem gravado inválido en línea {index}: tax_rate debe ser mayor a 0 cuando is_excluded=0.'
            )
        if not is_excluded and not tribute_id:
            raise FactusValidationError(
                f'Ítem gravado inválido en línea {index}: tribute_id es obligatorio para evitar degradación en Factus.'
            )
        if not is_excluded and (taxable_amount <= Decimal('0.00') or tax_amount <= Decimal('0.00')):
            raise FactusValidationError(
                f'Ítem gravado inválido en línea {index}: taxable_amount y tax_amount deben ser mayores a 0.'
            )
        if is_excluded and int(tribute_id or 0) != excluded_tribute_id:
            raise FactusValidationError(
                f'Ítem excluido inválido en línea {index}: tribute_id debe ser {excluded_tribute_id} (no causa/excluido).'
            )
        if not is_excluded:
            taxable_count += 1
    logger.info(
        'facturar_venta.payload_consistencia venta_id=%s customer_tribute_id=%s taxable_items=%s total_items=%s',
        venta.id,
        customer.get('tribute_id'),
        taxable_count,
        len(items),
    )


def _mark_factura_persistence_error(
    *,
    factura_id: int,
    venta_id: int,
    payload: dict[str, Any],
    numero: str,
    reference_code: str,
    triggered_by: Usuario | None,
    response: dict[str, Any] | None,
    response_show: dict[str, Any] | None,
    response_download: dict[str, Any] | None,
    fields: dict[str, str],
    bill_errors: list[str],
    error_message: str,
) -> FacturaElectronica:
    with transaction.atomic():
        factura = FacturaElectronica.objects.select_for_update().get(pk=factura_id)
        factura.estado_electronico = 'ERROR_PERSISTENCIA'
        safe_assign_charfield(factura, 'codigo_error', 'ERROR_PERSISTENCIA_SAVE')
        factura.mensaje_error = error_message
        safe_assign_json(
            factura,
            'response_json',
            _build_attempt_trace(
                factura=factura,
                payload=payload,
                numero=numero,
                reference_code=reference_code,
                triggered_by=triggered_by,
                status='ERROR_PERSISTENCIA',
                response=response,
                response_show=response_show,
                response_download=response_download,
                final_fields={**fields, 'persist_error': True},
                bill_errors=bill_errors,
                error={'message': error_message, 'stage': 'persist_factura'},
            ),
        )
        log_model_string_overflow_diagnostics(
            instance=factura, venta_id=venta_id, factura_id=factura.pk, stage='mark_persistence_error'
        )
        factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'updated_at'])
        return factura


def facturar_venta(
    venta_id: int,
    triggered_by: Usuario | None = None,
    *,
    force_resend_pending: bool = False,
) -> FacturaElectronica:
    logger.info('facturar_venta.inicio venta_id=%s user_id=%s', venta_id, getattr(triggered_by, 'id', None))
    with transaction.atomic():
        venta = (
            Venta.objects.select_for_update()
            .select_related('cliente')
            .prefetch_related('detalles__producto')
            .get(pk=venta_id)
        )
        if venta.tipo_comprobante != 'FACTURA':
            raise FactusValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
        if venta.estado == 'ANULADA':
            raise FactusValidationError('La venta está anulada y no se puede enviar a Factus.')
        if venta.estado not in {'COBRADA', 'FACTURADA'}:
            raise FactusValidationError('La venta debe estar en estado COBRADA antes de enviarse a Factus.')

        factura_existente = FacturaElectronica.objects.select_for_update().filter(venta=venta).first()
        if (
            factura_existente
            and factura_existente.estado_electronico in FINAL_ACCEPTED_STATUSES
            and has_definitive_electronic_identifiers(factura_existente)
        ):
            if venta.factura_electronica_uuid and venta.factura_electronica_uuid != factura_existente.uuid:
                logger.warning(
                    'facturar_venta.venta_uuid_historico_preservado venta_id=%s venta_uuid=%s factura_uuid=%s',
                    venta.id,
                    venta.factura_electronica_uuid,
                    factura_existente.uuid,
                )
            if venta.factura_electronica_cufe and venta.factura_electronica_cufe != factura_existente.cufe:
                logger.warning(
                    'facturar_venta.venta_cufe_historico_preservado venta_id=%s venta_cufe=%s factura_cufe=%s',
                    venta.id,
                    venta.factura_electronica_cufe,
                    factura_existente.cufe,
                )
            if not venta.factura_electronica_uuid or not venta.factura_electronica_cufe or not venta.fecha_envio_dian:
                venta.factura_electronica_uuid = venta.factura_electronica_uuid or (factura_existente.uuid or '')
                venta.factura_electronica_cufe = venta.factura_electronica_cufe or (factura_existente.cufe or '')
                venta.fecha_envio_dian = venta.fecha_envio_dian or factura_existente.updated_at
                venta.save(
                    update_fields=['factura_electronica_uuid', 'factura_electronica_cufe', 'fecha_envio_dian', 'updated_at']
                )
            logger.info(
                'facturar_venta.reutiliza_aceptada_historial_preservado venta_id=%s factura=%s '
                'uuid=%s cufe=%s range_change_ignored=true',
                venta.id,
                factura_existente.number,
                factura_existente.uuid,
                factura_existente.cufe,
            )
            try:
                if not factura_existente.xml_local_path:
                    download_xml(factura_existente)
            except DescargaFacturaError:
                logger.warning(
                    'facturar_venta.reutiliza_aceptada_xml_descarga_error venta_id=%s factura=%s',
                    venta.id,
                    factura_existente.number,
                    exc_info=True,
                )
            try:
                if not factura_existente.pdf_local_path:
                    download_pdf(factura_existente)
            except DescargaFacturaError:
                logger.warning(
                    'facturar_venta.reutiliza_aceptada_pdf_descarga_error venta_id=%s factura=%s',
                    venta.id,
                    factura_existente.number,
                    exc_info=True,
                )
            return factura_existente
        if (
            factura_existente
            and factura_existente.estado_electronico in FINAL_ACCEPTED_STATUSES
            and (venta.factura_electronica_uuid or venta.factura_electronica_cufe)
        ):
            logger.info(
                'facturar_venta.reenvio_bloqueado_documento_historico venta_id=%s factura_id=%s '
                'uuid=%s cufe=%s motivo=documento_aceptado_preservado',
                venta.id,
                factura_existente.pk,
                factura_existente.uuid,
                factura_existente.cufe,
            )
            return factura_existente
        if factura_existente and factura_existente.cufe and factura_existente.estado_electronico not in FINAL_ACCEPTED_STATUSES:
            raise FactusValidationError(
                f'La venta {venta.id} ya tiene CUFE persistido ({factura_existente.cufe}) en estado {factura_existente.estado_electronico}. '
                'No se permite una nueva asociación automática.'
            )
        if factura_existente and factura_existente.estado_electronico == 'PENDIENTE_REINTENTO' and not force_resend_pending:
            logger.info('facturar_venta.reutiliza_en_proceso venta_id=%s numero=%s', venta.id, factura_existente.number)
            return sync_existing_pending_invoice(factura=factura_existente, venta=venta, triggered_by=triggered_by)
        if factura_existente and factura_existente.estado_electronico == 'PENDIENTE_REINTENTO' and force_resend_pending:
            logger.warning('facturar_venta.reenvio_forzado_en_proceso venta_id=%s numero=%s', venta.id, factura_existente.number)

        local_totals = sync_sale_totals_before_emit(venta)
        payload = _build_and_log_factus_payload(venta)
        rango_activo = resolve_numbering_range(document_code='FACTURA_VENTA')
        validate_customer_for_factus(payload.get('customer', {}), venta)
        validate_payload_tax_consistency(payload, venta)
        logger.info(
            'facturar_venta.documento_local_normalizado venta_id=%s base=%s impuesto=%s total=%s',
            venta.id,
            local_totals['base_total'],
            local_totals['tax_total'],
            local_totals['total'],
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
            rango = resolve_numbering_range(document_code='FACTURA_VENTA')
            if not rango.factus_range_id:
                raise FactusValidationError(
                    'Debe sincronizar/configurar el rango antes de facturar. Falta factus_range_id del rango seleccionado.'
                )
            payload['numbering_range_id'] = int(rango.factus_range_id)

        should_lock_expected_number = number_matches_active_range(numero, rango_activo.prefijo)
        if should_lock_expected_number:
            payload['number'] = numero
        else:
            payload.pop('number', None)
        reference_code = resolve_reference_code(venta=venta, factura_existente=factura_existente, numero=numero)
        payload['reference_code'] = reference_code
        if FacturaElectronica.objects.filter(reference_code=reference_code).exclude(venta=venta).exists():
            raise FacturaDuplicadaError(f'Ya existe una factura electrónica con reference_code={reference_code}.')

        factura, _ = FacturaElectronica.objects.update_or_create(
            venta=venta,
            defaults={
                # Fuente canónica: solo estado_electronico.
                # `status` legado se sincroniza automáticamente en FacturaElectronica.save().
                'estado_electronico': 'PENDIENTE_REINTENTO',
                'number': numero,
                'reference_code': reference_code,
                'response_json': build_attempt_trace(
                    factura=factura_existente,
                    payload=payload,
                    numero=numero,
                    reference_code=reference_code,
                    triggered_by=triggered_by,
                    status='PENDIENTE_REINTENTO',
                ),
                'codigo_error': '',
                'mensaje_error': '',
            },
        )

    ctx = FacturacionContext(
        venta=venta,
        factura_existente=factura_existente,
        factura=factura,
        triggered_by=triggered_by,
        payload=payload,
        numero=numero,
        reference_code=reference_code,
        should_lock_expected_number=should_lock_expected_number,
    )

    client = FactusClient()
    try:
        for index, item in enumerate(ctx.payload.get('items', []), start=1):
            if not isinstance(item, dict):
                continue
            logger.info(
                'facturar_venta.payload_pre_post_item venta_id=%s line=%s tax_rate=%s is_excluded=%s tribute_id=%s',
                ctx.venta.id,
                index,
                item.get('tax_rate'),
                item.get('is_excluded'),
                item.get('tribute_id'),
            )
        logger.info(
            'facturar_venta.payload_pre_post venta_id=%s payload=%s items=%s customer=%s payment_form=%s '
            'payment_method=%s numbering_range_id=%s operation_type=%s',
            ctx.venta.id,
            ctx.payload,
            ctx.payload.get('items', []),
            ctx.payload.get('customer', {}),
            ctx.payload.get('payment_form'),
            ctx.payload.get('payment_method_code'),
            ctx.payload.get('numbering_range_id'),
            ctx.payload.get('operation_type'),
        )
        response_json = client.create_and_validate_invoice(ctx.payload)
    except FactusPendingDianError as exc:
        logger.warning(
            'facturar_venta.factus_409_pendiente_dian venta_id=%s numero=%s reference_code=%s',
            ctx.venta.id,
            ctx.numero,
            ctx.reference_code,
        )
        persist_pending_dian_conflict(
            factura=ctx.factura,
            payload=ctx.payload,
            numero=ctx.numero,
            reference_code=ctx.reference_code,
            triggered_by=ctx.triggered_by,
            error=exc,
        )
        return ctx.factura
    except (FactusAPIError, FactusAuthError) as exc:
        persist_remote_error(
            factura=ctx.factura,
            payload=ctx.payload,
            numero=ctx.numero,
            reference_code=ctx.reference_code,
            triggered_by=ctx.triggered_by,
            stage='send_invoice',
            error=exc,
        )
        if isinstance(exc, FactusAPIError):
            rejection = str(getattr(exc, 'provider_detail', '') or '')
            if 'FAK21' in rejection:
                logger.warning(
                    'facturar_venta.rechazo_cliente_sin_id venta_id=%s cliente_id=%s numero=%s resumen=FAK21',
                    ctx.venta.id,
                    ctx.venta.cliente_id,
                    ctx.numero,
                )
        logger.warning('facturar_venta.factus_rechazo venta_id=%s numero=%s', ctx.venta.id, ctx.numero)
        raise
    logger.info('facturar_venta.factus_response venta_id=%s keys=%s', ctx.venta.id, sorted(response_json.keys()))

    fields = extract_factus_data(response_json)
    fields['number'] = fields.get('number') or ctx.numero
    fields['reference_code'] = fields.get('reference_code') or ctx.reference_code
    pending_conciliation_error: FactusValidationError | None = None
    try:
        assert_emitted_document_matches_sale(
            venta=ctx.venta,
            fields=fields,
            expected_number=ctx.numero if ctx.should_lock_expected_number else '',
            expected_reference_code=ctx.reference_code,
        )
    except FactusValidationError as exc:
        persist_local_validation_error(
            factura=ctx.factura,
            payload=ctx.payload,
            numero=ctx.numero,
            reference_code=ctx.reference_code,
            triggered_by=ctx.triggered_by,
            error=exc,
            response=response_json,
        )
        raise
    try:
        assert_document_conciliation(
            venta=ctx.venta,
            request_payload=ctx.payload,
            response_payload=response_json,
            logger_context=fields,
        )
    except FactusValidationError as exc:
        pending_conciliation_error = exc
    bill_errors = _extract_bill_errors(response_json)

    response_show_json: dict[str, Any] | None = None
    response_download_json: dict[str, Any] | None = None
    missing_before = [field for field in ['uuid', 'xml_url', 'pdf_url'] if not fields.get(field)]
    if missing_before or pending_conciliation_error is not None:
        logger.info(
            'facturar_venta.factus_complemento_inicio venta_id=%s numero=%s faltantes=%s',
            ctx.venta.id,
            fields['number'],
            missing_before,
        )
        try:
            response_show_json = client.get_invoice(fields['number'])
        except (FactusAPIError, FactusAuthError) as exc:
            persist_remote_error(
                factura=ctx.factura,
                payload=ctx.payload,
                numero=ctx.numero,
                reference_code=ctx.reference_code,
                triggered_by=ctx.triggered_by,
                stage='get_invoice',
                error=exc,
            )
            raise
        logger.info(
            'facturar_venta.factus_show_response venta_id=%s numero=%s keys=%s',
            ctx.venta.id,
            fields['number'],
            sorted(response_show_json.keys()),
        )
        fields = merge_factus_fields(fields, extract_factus_data(response_show_json))
        try:
            assert_emitted_document_matches_sale(
                venta=ctx.venta,
                fields=fields,
                expected_number=ctx.numero if ctx.should_lock_expected_number else '',
                expected_reference_code=ctx.reference_code,
            )
            assert_document_conciliation(
                venta=ctx.venta,
                request_payload=ctx.payload,
                response_payload=response_show_json,
                logger_context=fields,
            )
        except FactusValidationError as exc:
            persist_local_validation_error(
                factura=ctx.factura,
                payload=ctx.payload,
                numero=ctx.numero,
                reference_code=ctx.reference_code,
                triggered_by=ctx.triggered_by,
                error=exc,
                response=response_json,
                response_show=response_show_json,
            )
            raise
        if not bill_errors:
            bill_errors = _extract_bill_errors(response_show_json)
        missing_after_show = [field for field in ['uuid', 'xml_url', 'pdf_url'] if not fields.get(field)]
        if missing_after_show:
            try:
                response_download_json = client.get_invoice_downloads(fields['number'])
                logger.info(
                    'facturar_venta.factus_download_response venta_id=%s numero=%s keys=%s',
                    ctx.venta.id,
                    fields['number'],
                    sorted(response_download_json.keys()),
                )
                fields = merge_factus_fields(fields, extract_factus_data(response_download_json))
                try:
                    assert_emitted_document_matches_sale(
                        venta=ctx.venta,
                        fields=fields,
                        expected_number=ctx.numero if ctx.should_lock_expected_number else '',
                        expected_reference_code=ctx.reference_code,
                    )
                    assert_document_conciliation(
                        venta=ctx.venta,
                        request_payload=ctx.payload,
                        response_payload=response_download_json,
                        logger_context=fields,
                    )
                except FactusValidationError as exc:
                    persist_local_validation_error(
                        factura=ctx.factura,
                        payload=ctx.payload,
                        numero=ctx.numero,
                        reference_code=ctx.reference_code,
                        triggered_by=ctx.triggered_by,
                        error=exc,
                        response=response_json,
                        response_show=response_show_json,
                        response_download=response_download_json,
                    )
                    raise
                if not bill_errors:
                    bill_errors = _extract_bill_errors(response_download_json)
            except (FactusAPIError, FactusAuthError) as exc:
                persist_remote_error(
                    factura=ctx.factura,
                    payload=ctx.payload,
                    numero=ctx.numero,
                    reference_code=ctx.reference_code,
                    triggered_by=ctx.triggered_by,
                    stage='get_invoice_downloads',
                    error=exc,
                )
                raise
    elif pending_conciliation_error is not None:
        persist_local_validation_error(
            factura=ctx.factura,
            payload=ctx.payload,
            numero=ctx.numero,
            reference_code=ctx.reference_code,
            triggered_by=ctx.triggered_by,
            error=pending_conciliation_error,
            response=response_json,
        )
        raise pending_conciliation_error

    if not fields.get('uuid'):
        fields['uuid'] = fields.get('cufe') or fields.get('reference_code') or fields['number']
    if not fields.get('xml_url'):
        fields['xml_url'] = f'{client.base_url}{client.bill_download_xml_path.format(number=fields["number"])}'
    if not fields.get('pdf_url'):
        fields['pdf_url'] = f'{client.base_url}{client.bill_download_pdf_path.format(number=fields["number"])}'

    required_fields = ['cufe', 'number', 'uuid', 'xml_url', 'pdf_url']
    missing_fields = [field for field in required_fields if not fields[field]]
    if missing_fields:
        factura.estado_electronico = 'ERROR_PERSISTENCIA'
        safe_assign_charfield(factura, 'codigo_error', 'RESPUESTA_INCOMPLETA')
        factura.mensaje_error = f'Factus no devolvió campos requeridos: {", ".join(missing_fields)}.'
        safe_assign_json(
            ctx.factura,
            'response_json',
            build_attempt_trace(
                factura=ctx.factura,
                payload=ctx.payload,
                numero=ctx.numero,
                reference_code=ctx.reference_code,
                triggered_by=ctx.triggered_by,
                status='ERROR_PERSISTENCIA',
                response=response_json,
                response_show=response_show_json,
                response_download=response_download_json,
                final_fields=fields,
                bill_errors=bill_errors,
                error={'message': 'Respuesta incompleta de Factus', 'missing_fields': missing_fields},
            ),
        )
        log_model_string_overflow_diagnostics(
            instance=factura, venta_id=venta.id, factura_id=factura.pk, stage='missing_required_fields'
        )
        factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])
        logger.error(
            'facturar_venta.respuesta_incompleta venta_id=%s numero=%s faltantes=%s',
            venta.id,
            fields.get('number') or numero,
            missing_fields,
        )
        ctx.factura.save(update_fields=['status', 'estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])
        logger.error('facturar_venta.respuesta_incompleta venta_id=%s numero=%s faltantes=%s', ctx.venta.id, fields.get('number') or ctx.numero, missing_fields)
        raise FactusAPIError('La respuesta de Factus no contiene todos los datos requeridos.')

    persistable_fields = {k: v for k, v in fields.items() if k in PERSISTABLE_FACTURA_FIELDS}

    try:
        with transaction.atomic():
            ctx.factura = FacturaElectronica.objects.select_for_update().get(pk=ctx.factura.pk)
            for key, value in persistable_fields.items():
                if key == 'qr':
                    ctx.factura.qr_data = value
                elif key == 'qr_image':
                    assign_qr_image_fields(ctx.factura, value)
                else:
                    if key in {'xml_url', 'pdf_url', 'public_url'}:
                        safe_assign_charfield(ctx.factura, key, value)
                    else:
                        setattr(factura, key, value)
            factura.reference_code = persistable_fields.get('reference_code') or reference_code
            factura.estado_electronico = persistable_fields.get('status', 'ERROR_INTEGRACION')
            factura.estado_factus_raw = persistable_fields.get('estado_factus_raw', factura.estado_factus_raw)
            factura.emitida_en_factus = bool(factura.number and factura.cufe)
            codigo_error = (
                'OBSERVACIONES_FACTUS'
                if bill_errors and persistable_fields.get('status') == 'ACEPTADA'
                else response_json.get('error_code')
            )
            safe_assign_charfield(factura, 'codigo_error', codigo_error)
            factura.mensaje_error = (
                '; '.join(bill_errors)
                if bill_errors
                else response_json.get('error_message')
            )
            safe_assign_json(
                ctx.factura,
                'response_json',
                build_attempt_trace(
                    factura=ctx.factura,
                    payload=ctx.payload,
                    numero=ctx.numero,
                    reference_code=ctx.reference_code,
                    triggered_by=ctx.triggered_by,
                    status=persistable_fields.get('status', 'ERROR_INTEGRACION'),
                    response=response_json,
                    response_show=response_show_json,
                    response_download=response_download_json,
                    final_fields={**fields, 'persisted_fields': persistable_fields},
                    bill_errors=bill_errors,
                ),
            )
            ctx.factura.observaciones_json = bill_errors
            ctx.factura.retry_count = int(ctx.factura.retry_count or 0) + 1
            ctx.factura.last_retry_at = timezone.now()
            ctx.factura.next_retry_at = None
            ctx.factura.ultima_sincronizacion_at = timezone.now()
            overflows = log_model_string_overflow_diagnostics(
                instance=ctx.factura, venta_id=ctx.venta.id, factura_id=ctx.factura.pk, stage='before_factura_save'
            )
            if overflows:
                raise FacturaPersistenciaError('Se detectaron campos con overflow antes de guardar la factura.')
            ctx.factura.save()

            incoming_uuid = fields.get('uuid') or ''
            incoming_cufe = fields.get('cufe') or ''
            if not ctx.venta.factura_electronica_uuid:
                ctx.venta.factura_electronica_uuid = incoming_uuid
            elif incoming_uuid and ctx.venta.factura_electronica_uuid != incoming_uuid:
                logger.warning(
                    'facturar_venta.no_sobrescribe_venta_uuid_historico venta_id=%s actual=%s incoming=%s',
                    ctx.venta.id,
                    ctx.venta.factura_electronica_uuid,
                    incoming_uuid,
                )
            if not ctx.venta.factura_electronica_cufe:
                ctx.venta.factura_electronica_cufe = incoming_cufe
            elif incoming_cufe and ctx.venta.factura_electronica_cufe != incoming_cufe:
                logger.warning(
                    'facturar_venta.no_sobrescribe_venta_cufe_historico venta_id=%s actual=%s incoming=%s',
                    ctx.venta.id,
                    ctx.venta.factura_electronica_cufe,
                    incoming_cufe,
                )
            ctx.venta.fecha_envio_dian = ctx.venta.fecha_envio_dian or ctx.factura.updated_at
            ctx.venta.save(update_fields=['factura_electronica_uuid', 'factura_electronica_cufe', 'fecha_envio_dian', 'updated_at'])
            logger.info(
                'facturar_venta.persistida venta_id=%s factura=%s status=%s reference_code=%s',
                venta.id,
                factura.number,
                factura.estado_electronico,
                factura.reference_code,
            )
            if ctx.factura.cufe and ctx.factura.number:
                qr_file = generate_qr_dian(ctx.factura.number, ctx.factura.cufe)
                ctx.factura.qr.save(qr_file.name, qr_file, save=False)
                ctx.factura.save(update_fields=['qr', 'updated_at'])
    except (DataError, FacturaPersistenciaError) as exc:
        with transaction.atomic():
            factura = FacturaElectronica.objects.select_for_update().get(pk=factura.pk)
            factura.estado_electronico = 'ERROR_PERSISTENCIA'
            safe_assign_charfield(factura, 'codigo_error', 'ERROR_PERSISTENCIA_SAVE')
            factura.mensaje_error = (
                'No se pudo persistir la factura electrónica por un límite de almacenamiento. '
                'Revise logs técnicos para detalle de campos.'
            )
            log_model_string_overflow_diagnostics(
                instance=ctx.factura, venta_id=ctx.venta.id, factura_id=ctx.factura.pk, stage='dataerror_factura_save'
            )
            factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'updated_at'])
        raise DataError(str(exc))

    ctx.factura.send_email_enabled = bool(ctx.payload.get('send_email', True))
    ctx.factura.save(update_fields=['send_email_enabled', 'updated_at'])
    try:
        sync_invoice_assets(ctx.factura, include_email_content=not ctx.factura.send_email_enabled)
    except DescargaFacturaError:
        logger.warning('facturar_venta.assets_sync_error venta_id=%s factura=%s', ctx.venta.id, ctx.factura.number, exc_info=True)
    logger.info(
        'facturar_venta.emitida_ok venta_id=%s factura_id=%s numero=%s estado=%s',
        venta.id,
        factura.pk,
        factura.number,
        factura.estado_electronico,
    )
    upload_custom_pdf_to_factus(ctx.factura)
    send_invoice_email_via_factus(ctx.factura)
    logger.info('facturar_venta.fin_ok venta_id=%s factura=%s', ctx.venta.id, ctx.factura.number)
    return ctx.factura
