from __future__ import annotations

import copy
import hashlib
import json
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.factus_client import FactusAPIError, FactusPendingDianError
from apps.facturacion.services.persistence_safety import (
    log_model_string_overflow_diagnostics,
    normalize_qr_image_value,
    safe_assign_charfield,
    safe_assign_json,
)
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)
MISMATCH_ERROR_CODE = 'MISMATCH_NUMERACION'
LOCAL_VALIDATION_ERROR_CODE = 'ERROR_VALIDACION_LOCAL'
DOCUMENT_CONCILIATION_ERROR_CODE = 'ERROR_CONCILIACION_DOCUMENTAL'


def assign_qr_image_fields(factura: FacturaElectronica, qr_image_value: str) -> None:
    qr_image_url, qr_image_data = normalize_qr_image_value(qr_image_value)
    safe_assign_charfield(factura, 'qr_image_url', qr_image_url)
    factura.qr_image_data = qr_image_data


def build_attempt_trace(
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
    payload_sent = copy.deepcopy(payload)
    payload_hash = hashlib.sha256(
        json.dumps(payload_sent, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    ).hexdigest()
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
    venta_snapshot = None
    if factura and factura.venta_id:
        venta_obj = Venta.objects.filter(pk=factura.venta_id).prefetch_related('detalles__producto').first()
        if venta_obj is not None:
            venta_snapshot = {
                'id': venta_obj.id,
                'numero_comprobante': venta_obj.numero_comprobante,
                'subtotal': str(venta_obj.subtotal),
                'iva': str(venta_obj.iva),
                'descuento_valor': str(venta_obj.descuento_valor),
                'total': str(venta_obj.total),
                'detalles': [
                    {
                        'producto_id': d.producto_id,
                        'codigo': getattr(d.producto, 'codigo', ''),
                        'nombre': getattr(d.producto, 'nombre', ''),
                        'cantidad': str(d.cantidad),
                        'precio_unitario': str(d.precio_unitario),
                        'descuento_unitario': str(d.descuento_unitario),
                        'subtotal': str(d.subtotal),
                        'iva_porcentaje': str(d.iva_porcentaje),
                        'total': str(d.total),
                    }
                    for d in venta_obj.detalles.all()
                ],
            }
    return {
        'request': payload_sent,
        'request_sha256': payload_hash,
        'response': response,
        'response_show': response_show,
        'response_download': response_download,
        'final_fields': final_fields or {},
        'bill_errors': bill_errors or [],
        'venta_id': factura.venta_id if factura else None,
        'venta_snapshot': venta_snapshot,
        'triggered_by_user_id': triggered_by.id if triggered_by else None,
        'attempts': attempts,
    }


def retry_metadata(factura: FacturaElectronica, *, pending: bool) -> dict[str, Any]:
    retry_count = int((factura.retry_count or 0) + 1)
    now = timezone.now()
    return {
        'retry_count': retry_count,
        'last_retry_at': now,
        'next_retry_at': now if pending else None,
    }


def persist_local_validation_error(
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
    if factura.status == 'ACEPTADA' and factura.cufe:
        logger.error(
            'facturar_venta.local_validation_conflict_ignored venta_id=%s factura_id=%s numero=%s',
            factura.venta_id,
            factura.pk,
            factura.number,
        )
        return

    factura.status = 'RECHAZADA'
    factura.estado_electronico = 'RECHAZADA'
    error_text = str(error)
    if DOCUMENT_CONCILIATION_ERROR_CODE in error_text:
        factura.codigo_error = DOCUMENT_CONCILIATION_ERROR_CODE
    elif 'devolvió number=' in error_text:
        factura.codigo_error = MISMATCH_ERROR_CODE
    else:
        factura.codigo_error = LOCAL_VALIDATION_ERROR_CODE
    factura.mensaje_error = error_text
    factura.response_json = build_attempt_trace(
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
    metadata = retry_metadata(factura, pending=False)
    factura.retry_count = metadata['retry_count']
    factura.last_retry_at = metadata['last_retry_at']
    factura.next_retry_at = metadata['next_retry_at']
    factura.save(update_fields=['status', 'estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])


def persist_remote_error(
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
    factura.status = 'RECHAZADA' if is_validation_error else 'ERROR_INTEGRACION'
    factura.estado_electronico = factura.status
    safe_assign_charfield(factura, 'codigo_error', str(status_code or error.__class__.__name__))
    factura.mensaje_error = provider_detail or str(error)
    safe_assign_json(
        factura,
        'response_json',
        build_attempt_trace(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            status=factura.status,
            error={
                'stage': stage,
                'error_type': error.__class__.__name__,
                'message': str(error),
                'status_code': status_code,
                'provider_detail': provider_detail,
            },
        ),
    )
    metadata = retry_metadata(factura, pending=not is_validation_error)
    factura.retry_count = metadata['retry_count']
    factura.last_retry_at = metadata['last_retry_at']
    factura.next_retry_at = metadata['next_retry_at']
    log_model_string_overflow_diagnostics(
        instance=factura, venta_id=factura.venta_id, factura_id=factura.pk, stage='persist_remote_error'
    )
    factura.save(update_fields=['status', 'estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])


def persist_pending_dian_conflict(
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
    factura.status = 'PENDIENTE_REINTENTO'
    factura.estado_electronico = 'PENDIENTE_REINTENTO'
    safe_assign_charfield(factura, 'codigo_error', 'FACTUS_PENDING_DIAN_409')
    factura.mensaje_error = message
    safe_assign_json(
        factura,
        'response_json',
        build_attempt_trace(
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
    metadata = retry_metadata(factura, pending=True)
    factura.retry_count = metadata['retry_count']
    factura.last_retry_at = metadata['last_retry_at']
    factura.next_retry_at = metadata['next_retry_at']
    log_model_string_overflow_diagnostics(
        instance=factura, venta_id=factura.venta_id, factura_id=factura.pk, stage='persist_pending_dian_conflict'
    )
    factura.save(update_fields=['status', 'estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'retry_count', 'last_retry_at', 'next_retry_at', 'updated_at'])


def mark_factura_persistence_error(
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
        factura.status = 'ERROR_PERSISTENCIA'
        factura.estado_electronico = 'ERROR_PERSISTENCIA'
        safe_assign_charfield(factura, 'codigo_error', 'ERROR_PERSISTENCIA_SAVE')
        factura.mensaje_error = error_message
        safe_assign_json(
            factura,
            'response_json',
            build_attempt_trace(
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
        factura.save(update_fields=['status', 'estado_electronico', 'codigo_error', 'mensaje_error', 'response_json', 'updated_at'])
        return factura
