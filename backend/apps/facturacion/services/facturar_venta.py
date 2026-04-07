"""Servicio de alto nivel para facturar una venta en Factus."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import DataError, transaction
from django.utils import timezone

from apps.facturacion.exceptions import FacturaDuplicadaError, FacturaPersistenciaError
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.consecutivo_service import get_next_invoice_sequence, resolve_numbering_range
from apps.facturacion.services.document_totals import (
    calculate_document_detail_totals,
    q_money,
)
from apps.facturacion.services.electronic_state_machine import extract_bill_errors as _extract_bill_errors
from apps.facturacion.services.electronic_state_machine import map_factus_status
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factura_assets_service import sync_invoice_assets
from apps.facturacion.services.factus_catalog_lookup import get_tribute_id
from apps.facturacion.services.factus_client import (
    FactusAPIError,
    FactusAuthError,
    FactusClient,
    FactusPendingDianError,
    FactusValidationError,
)
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.generate_qr_dian import generate_qr_dian
from apps.facturacion.services.persistence_safety import (
    log_model_string_overflow_diagnostics,
    normalize_qr_image_value,
    safe_assign_charfield,
    safe_assign_json,
)
from apps.facturacion.services.upload_custom_pdf_to_factus import (
    send_invoice_email_via_factus,
    upload_custom_pdf_to_factus,
)
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)
MISMATCH_ERROR_CODE = 'MISMATCH_NUMERACION'
LOCAL_VALIDATION_ERROR_CODE = 'ERROR_VALIDACION_LOCAL'
DOCUMENT_CONCILIATION_ERROR_CODE = 'ERROR_CONCILIACION_DOCUMENTAL'
MONEY_TOLERANCE = Decimal('0.05')
MONEY_QUANT = Decimal('0.01')
FINAL_ACCEPTED_STATUSES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}


class FacturaPersistenciaError(Exception):
    """Error de persistencia controlado para no dejar estados ambiguos."""


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
        'status': map_factus_status(response_json)[0],
        'estado_factus_raw': map_factus_status(response_json)[1],
    }


def _merge_factus_fields(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    for key, value in extra.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def _assign_qr_image_fields(factura: FacturaElectronica, qr_image_value: str) -> None:
    qr_image_url, qr_image_data = normalize_qr_image_value(qr_image_value)
    safe_assign_charfield(factura, 'qr_image_url', qr_image_url)
    factura.qr_image_data = qr_image_data


PERSISTABLE_FACTURA_FIELDS = {
    'cufe',
    'uuid',
    'number',
    'reference_code',
    'xml_url',
    'pdf_url',
    'public_url',
    'qr',
    'qr_image',
    'status',
    'estado_factus_raw',
}


def _apply_qr_image_fields(instance: FacturaElectronica, raw_value: str) -> None:
    qr_image_url, qr_image_data = normalize_qr_image_value(raw_value)
    safe_assign_charfield(instance, 'qr_image_url', qr_image_url)
    instance.qr_image_data = qr_image_data


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


def _retry_metadata(factura: FacturaElectronica, *, pending: bool) -> dict[str, Any]:
    retry_count = int((factura.retry_count or 0) + 1)
    now = timezone.now()
    return {
        'retry_count': retry_count,
        'last_retry_at': now,
        'next_retry_at': now if pending else None,
    }


def _assert_emitted_document_matches_sale(
    *,
    venta: Venta,
    fields: dict[str, str],
    expected_number: str,
    expected_reference_code: str,
) -> None:
    number = str(fields.get('number') or '').strip()
    reference_code = str(fields.get('reference_code') or '').strip()
    expected_number = str(expected_number or '').strip()
    expected_reference_code = str(expected_reference_code or '').strip()

    expected_prefix = ''.join(char for char in expected_number if char.isalpha())
    expected_sequence = ''.join(char for char in expected_number if char.isdigit())
    returned_prefix = ''.join(char for char in number if char.isalpha())
    returned_sequence = ''.join(char for char in number if char.isdigit())
    has_prefix_mismatch = bool(expected_prefix and returned_prefix and expected_prefix != returned_prefix)
    has_sequence_mismatch = bool(expected_sequence and returned_sequence and expected_sequence != returned_sequence)

    logger.info(
        'facturar_venta.validacion_documental venta_id=%s expected_reference=%s expected_number=%s '
        'returned_number=%s returned_reference_code=%s factus_status=%s',
        venta.id,
        expected_reference_code,
        expected_number,
        number,
        reference_code,
        fields.get('status', ''),
    )

    if number and expected_number and (number != expected_number or has_prefix_mismatch or has_sequence_mismatch):
        raise FactusValidationError(
            f'Factus devolvió number={number} pero la venta {venta.id} esperaba {expected_number}. '
            'Se bloquea la asociación para evitar enlazar CUFE/QR de otro documento.'
        )

    if number and FacturaElectronica.objects.filter(number=number).exclude(venta=venta).exists():
        raise FactusValidationError(
            f'Factus devolvió number={number}, pero ya está asociado a otra venta. '
            'Se bloquea la asociación para evitar enlazar CUFE/QR de otro documento.'
        )

    if reference_code and expected_reference_code and reference_code != expected_reference_code:
        raise FactusValidationError(
            f'Factus devolvió reference_code={reference_code} pero la venta {venta.id} esperaba '
            f'{expected_reference_code}. Se bloquea la asociación para evitar cruces entre ventas.'
        )

    if reference_code and FacturaElectronica.objects.filter(reference_code=reference_code).exclude(venta=venta).exists():
        raise FactusValidationError(
            f'Factus devolvió reference_code={reference_code}, pero ya está asociado a otra venta. '
            'Se bloquea la asociación para evitar cruces entre ventas.'
        )


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _normalize_identification(value: Any) -> str:
    return ''.join(char for char in str(value or '').strip() if char.isalnum()).upper()


def _quantize_money(value: Decimal | None) -> Decimal:
    normalized = Decimal(str(value if value is not None else '0'))
    return normalized.quantize(MONEY_QUANT)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'si', 'sí', 'yes', 'y', 'on'}


def _extract_request_document_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    bill = data.get('bill', data) if isinstance(data, dict) else {}
    customer = bill.get('customer', data.get('customer', {})) if isinstance(bill, dict) else {}
    items = bill.get('items', data.get('items', [])) if isinstance(bill, dict) else []
    if not isinstance(customer, dict):
        customer = {}
    if not isinstance(items, list):
        items = []

    total = Decimal('0.00')
    tax_total = Decimal('0.00')
    base_total = Decimal('0.00')

    for item in items:
        if not isinstance(item, dict):
            continue
        quantity = _to_decimal_or_none(item.get('quantity')) or Decimal('0')
        unit_price = _to_decimal_or_none(item.get('price')) or Decimal('0')
        discount_rate = _to_decimal_or_none(item.get('discount_rate')) or Decimal('0')
        tax_rate = _to_decimal_or_none(item.get('tax_rate')) or Decimal('0')
        is_excluded = _to_bool(item.get('is_excluded'))

        line = calculate_document_detail_totals(
            quantity=quantity,
            unit_gross_price=unit_price,
            discount_pct=discount_rate,
            tax_pct=Decimal('0.00') if is_excluded else tax_rate,
        )
        total += line['total']
        base_total += line['base']
        tax_total += line['impuesto']

    return {
        'customer_identification': _normalize_identification(
            customer.get('identification') or customer.get('identification_number') or customer.get('nit')
        ),
        'total': _quantize_money(total),
        'tax_total': _quantize_money(tax_total),
        'base_total': _quantize_money(base_total),
        'items_count': len(items),
    }


def _calculate_sale_document_totals_from_details(venta: Venta) -> dict[str, Decimal]:
    base_total = Decimal('0.00')
    tax_total = Decimal('0.00')
    total = Decimal('0.00')

    for detalle in venta.detalles.all():
        line_total_bruto = q_money(q_money(detalle.cantidad) * q_money(detalle.precio_unitario))
        descuento_pct = Decimal('0.00')
        if line_total_bruto > Decimal('0.00'):
            descuento_linea = q_money(q_money(detalle.cantidad) * max(q_money(detalle.descuento_unitario), Decimal('0.00')))
            descuento_pct = q_money((descuento_linea / line_total_bruto) * Decimal('100'))
        tax_pct = q_money(detalle.iva_porcentaje) if q_money(detalle.iva_porcentaje) > Decimal('0.00') else Decimal('0.00')
        line = calculate_document_detail_totals(
            quantity=detalle.cantidad,
            unit_gross_price=detalle.precio_unitario,
            discount_pct=descuento_pct,
            tax_pct=tax_pct,
        )
        if q_money(detalle.subtotal) != line['base'] or q_money(detalle.total) != line['total']:
            detalle.subtotal = line['base']
            detalle.total = line['total']
            detalle.save(update_fields=['subtotal', 'total', 'updated_at'])
        logger.info(
            'facturar_venta.detalle_documental venta_id=%s detalle_id=%s cantidad=%s precio_bruto=%s descuento_pct=%s '
            'base=%s impuesto=%s total=%s',
            venta.id,
            detalle.id,
            detalle.cantidad,
            detalle.precio_unitario,
            descuento_pct,
            line['base'],
            line['impuesto'],
            line['total'],
        )
        base_total += line['base']
        tax_total += line['impuesto']
        total += line['total']

    return {
        'base_total': q_money(base_total),
        'tax_total': q_money(tax_total),
        'total': q_money(total),
    }


def _sync_sale_totals_before_emit(venta: Venta) -> dict[str, Decimal]:
    calculated = _calculate_sale_document_totals_from_details(venta)
    current_base = q_money(venta.subtotal)
    current_tax = q_money(venta.iva)
    current_total = q_money(venta.total)
    changed_fields: list[str] = []
    if current_base != calculated['base_total']:
        venta.subtotal = calculated['base_total']
        changed_fields.append('subtotal')
    if current_tax != calculated['tax_total']:
        venta.iva = calculated['tax_total']
        changed_fields.append('iva')
    if current_total != calculated['total']:
        venta.total = calculated['total']
        changed_fields.append('total')
    if changed_fields:
        venta.save(update_fields=[*changed_fields, 'updated_at'])
        logger.warning(
            'facturar_venta.totales_recalculados venta_id=%s changed=%s before=(%s,%s,%s) after=(%s,%s,%s)',
            venta.id,
            changed_fields,
            current_base,
            current_tax,
            current_total,
            calculated['base_total'],
            calculated['tax_total'],
            calculated['total'],
        )
    return calculated


def _extract_totals_from_items(items: list[Any]) -> dict[str, Decimal]:
    total = Decimal('0.00')
    tax_total = Decimal('0.00')
    base_total = Decimal('0.00')
    for item in items:
        if not isinstance(item, dict):
            continue
        quantity = _to_decimal_or_none(item.get('quantity') or item.get('qty')) or Decimal('0')
        unit_price = _to_decimal_or_none(
            item.get('price') or item.get('unit_price') or item.get('price_amount')
        ) or Decimal('0')
        discount_rate = _to_decimal_or_none(
            item.get('discount_rate') or item.get('discount_percentage')
        ) or Decimal('0')
        discount_amount_field = _to_decimal_or_none(
            item.get('discount_amount') or item.get('discount')
        ) or Decimal('0')
        tax_rate = _to_decimal_or_none(item.get('tax_rate') or item.get('tax_percentage')) or Decimal('0')
        is_excluded = _to_bool(item.get('is_excluded'))

        if discount_amount_field > Decimal('0.00'):
            gross_line = _quantize_money(quantity * unit_price)
            discount_rate = _quantize_money((discount_amount_field / gross_line) * Decimal('100')) if gross_line > Decimal('0.00') else Decimal('0.00')
        line = calculate_document_detail_totals(
            quantity=quantity,
            unit_gross_price=unit_price,
            discount_pct=discount_rate,
            tax_pct=Decimal('0.00') if is_excluded else tax_rate,
        )
        total += line['total']
        base_total += line['base']
        tax_total += line['impuesto']

    return {
        'total': _quantize_money(total),
        'base_total': _quantize_money(base_total),
        'tax_total': _quantize_money(tax_total),
    }


def _extract_remote_document_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    bill = data.get('bill', data) if isinstance(data, dict) else {}
    customer = bill.get('customer', data.get('customer', {})) if isinstance(bill, dict) else {}
    totals = bill.get('totals', data.get('totals', {})) if isinstance(bill, dict) else {}
    if not isinstance(customer, dict):
        customer = {}
    if not isinstance(totals, dict):
        totals = {}
    items = bill.get('items', data.get('items', [])) if isinstance(bill, dict) else []
    taxes = bill.get('tax_totals', data.get('tax_totals', [])) if isinstance(bill, dict) else []
    if not isinstance(items, list):
        items = []
    if not isinstance(taxes, list):
        taxes = []
    has_item_amounts = any(
        isinstance(item, dict)
        and any(
            item.get(key) not in (None, '')
            for key in (
                'price',
                'unit_price',
                'price_amount',
                'line_total',
                'total',
                'total_amount',
                'tax_rate',
                'tax_percentage',
                'tax_amount',
            )
        )
        for item in items
    )

    tax_total = _to_decimal_or_none(totals.get('tax_amount') or totals.get('tax') or totals.get('total_tax'))
    if tax_total is None:
        collected = [_to_decimal_or_none((t.get('tax_amount') if isinstance(t, dict) else None)) for t in taxes]
        tax_total = sum((val for val in collected if val is not None), Decimal('0')) if collected else None
    items_totals = _extract_totals_from_items(items)

    total_candidates = [
        _to_decimal_or_none(totals.get('payable_amount')),
        _to_decimal_or_none(totals.get('total_payable')),
        _to_decimal_or_none(totals.get('total')),
        _to_decimal_or_none(bill.get('total')),
        _to_decimal_or_none(data.get('total')),
        items_totals['total'],
    ]
    base_candidates = [
        _to_decimal_or_none(totals.get('taxable_amount')),
        _to_decimal_or_none(totals.get('subtotal')),
        _to_decimal_or_none(totals.get('line_extension_amount')),
        _to_decimal_or_none(totals.get('gross_value')),
        _to_decimal_or_none(bill.get('gross_value')),
        _to_decimal_or_none(data.get('gross_value')),
        items_totals['base_total'],
    ]
    tax_candidates = [
        tax_total,
        items_totals['tax_total'],
    ]

    return {
        'customer_identification': _normalize_identification(
            customer.get('identification') or customer.get('identification_number') or customer.get('nit')
        ),
        'total': next((v for v in total_candidates if v is not None), None),
        'tax_total': next((v for v in tax_candidates if v is not None), None),
        'base_total': next((v for v in base_candidates if v is not None), None),
        'total_candidates': [v for v in total_candidates if v is not None],
        'tax_total_candidates': [v for v in tax_candidates if v is not None],
        'base_total_candidates': [v for v in base_candidates if v is not None],
        'items_count': len(items),
        'has_item_amounts': has_item_amounts,
    }


def _extract_items_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    bill = data.get('bill', data) if isinstance(data, dict) else {}
    items = bill.get('items', data.get('items', [])) if isinstance(bill, dict) else []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _is_remote_snapshot_inconclusive(*, remote: dict[str, Any], expected_tax: Decimal) -> bool:
    remote_tax = _to_decimal_or_none(remote.get('tax_total'))
    remote_base = _to_decimal_or_none(remote.get('base_total'))
    remote_total = _to_decimal_or_none(remote.get('total'))
    items_count = int(remote.get('items_count') or 0)
    has_item_amounts = bool(remote.get('has_item_amounts'))
    tax_candidates = [v for v in (remote.get('tax_total_candidates') or []) if _to_decimal_or_none(v) is not None]

    if expected_tax <= Decimal('0.00'):
        return False
    if remote_tax is None or remote_total is None or remote_base is None:
        return False
    if remote_tax != Decimal('0.00'):
        return False
    if remote_total != remote_base:
        return False
    if has_item_amounts:
        return False
    if items_count > 0 and tax_candidates:
        return False
    return True


def _nearest_expected(candidates: list[Any], expected_value: Decimal) -> Decimal | None:
    normalized = [_to_decimal_or_none(value) for value in candidates]
    valid = [value for value in normalized if value is not None]
    if not valid:
        return None
    return min(valid, key=lambda current: abs(current - expected_value))


def _assert_document_conciliation(
    *,
    venta: Venta,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    logger_context: dict[str, Any],
) -> None:
    expected_snapshot = _extract_request_document_snapshot(request_payload)
    expected = _calculate_sale_document_totals_from_details(venta)
    remote = _extract_remote_document_snapshot(response_payload)

    raw_local_total = _to_decimal_or_none(venta.total) or Decimal('0')
    raw_local_tax = _to_decimal_or_none(venta.iva) or Decimal('0')
    raw_local_base = _to_decimal_or_none(venta.subtotal) or Decimal('0')

    expected_total = expected.get('total') or Decimal('0')
    expected_tax = expected.get('tax_total') or Decimal('0')
    expected_base = expected.get('base_total') or Decimal('0')
    expected_customer = _normalize_identification(expected_snapshot.get('customer_identification') or '')
    expected_items_count = int(expected_snapshot.get('items_count') or 0)
    remote_is_inconclusive = _is_remote_snapshot_inconclusive(remote=remote, expected_tax=expected_tax)

    mismatches: list[str] = []
    remote_total = _nearest_expected(remote.get('total_candidates', []), expected_total) or remote.get('total')
    if (
        not remote_is_inconclusive
        and remote_total is not None
        and abs(remote_total - expected_total) > MONEY_TOLERANCE
    ):
        mismatches.append(f'total_remoto={remote_total} total_esperado={expected_total}')

    remote_tax = _nearest_expected(remote.get('tax_total_candidates', []), expected_tax) or remote.get('tax_total')
    if (
        not remote_is_inconclusive
        and remote_tax is not None
        and abs(remote_tax - expected_tax) > MONEY_TOLERANCE
    ):
        mismatches.append(f'impuesto_remoto={remote_tax} impuesto_esperado={expected_tax}')

    remote_base = _nearest_expected(remote.get('base_total_candidates', []), expected_base) or remote.get('base_total')
    if (
        not remote_is_inconclusive
        and remote_base is not None
        and abs(remote_base - expected_base) > MONEY_TOLERANCE
    ):
        mismatches.append(f'base_remota={remote_base} base_esperada={expected_base}')

    remote_customer = str(remote.get('customer_identification') or '').strip()
    if remote_customer and expected_customer and remote_customer != expected_customer:
        mismatches.append(f'cliente_remoto={remote_customer} cliente_esperado={expected_customer}')

    remote_items_count = int(remote.get('items_count') or 0)
    if remote_items_count and expected_items_count and remote_items_count != expected_items_count:
        mismatches.append(f'items_remotos={remote_items_count} items_esperados={expected_items_count}')

    logger.info(
        'facturar_venta.conciliacion venta_id=%s factura_number=%s reference_code=%s '
        'total_local=%s total_esperado=%s total_remoto=%s '
        'base_local=%s base_esperada=%s base_remota=%s '
        'impuesto_local=%s impuesto_esperado=%s impuesto_remoto=%s '
        'cliente_remoto=%s cliente_esperado=%s resultado=%s',
        venta.id,
        logger_context.get('number', ''),
        logger_context.get('reference_code', ''),
        raw_local_total,
        expected_total,
        remote_total,
        raw_local_base,
        expected_base,
        remote_base,
        raw_local_tax,
        expected_tax,
        remote_tax,
        remote_customer,
        expected_customer,
        'OK' if not mismatches else 'MISMATCH',
    )
    if mismatches:
        request_items = _extract_items_from_payload(request_payload)
        response_items = _extract_items_from_payload(response_payload)
        logger.error(
            'facturar_venta.conciliacion_error venta_id=%s payload_enviado=%s item_original=%s item_factus=%s '
            'totales_locales=%s totales_factus=%s response_json=%s',
            venta.id,
            request_payload,
            request_items[0] if request_items else {},
            response_items[0] if response_items else {},
            {
                'base': str(expected_base),
                'impuesto': str(expected_tax),
                'total': str(expected_total),
            },
            {
                'base': str(remote_base),
                'impuesto': str(remote_tax),
                'total': str(remote_total),
            },
            response_payload,
        )
    if remote_is_inconclusive:
        logger.warning(
            'facturar_venta.conciliacion_inconclusa venta_id=%s factura_number=%s reference_code=%s '
            'total_esperado=%s impuesto_esperado=%s base_esperada=%s '
            'total_remoto=%s impuesto_remoto=%s base_remota=%s',
            venta.id,
            logger_context.get('number', ''),
            logger_context.get('reference_code', ''),
            expected_total,
            expected_tax,
            expected_base,
            remote_total,
            remote_tax,
            remote_base,
        )
    if mismatches:
        request_reference_code = str(request_payload.get('reference_code') or '').strip()
        returned_reference_code = str(logger_context.get('reference_code') or '').strip()
        collision_hint = ''
        if request_reference_code and returned_reference_code and request_reference_code == returned_reference_code:
            collision_hint = (
                ' Posible colisión por reuse de reference_code: Factus respondió un documento previo '
                'con el mismo reference_code técnico pero con totales/ítems distintos.'
            )
        raise FactusValidationError(
            f'{DOCUMENT_CONCILIATION_ERROR_CODE}: Conciliación documental fallida ({", ".join(mismatches)}).'
            f'{collision_hint}'
        )


def _build_and_log_factus_payload(venta: Venta) -> dict[str, Any]:
    """
    Separa explícitamente la traducción al formato Factus del resto del flujo.
    La capa documental local se normaliza antes con _sync_sale_totals_before_emit.
    """
    payload = build_invoice_payload(venta)
    customer = payload.get('customer', {}) if isinstance(payload.get('customer'), dict) else {}
    items = payload.get('items', []) if isinstance(payload.get('items'), list) else []
    first_item = items[0] if items and isinstance(items[0], dict) else {}
    logger.info(
        'facturar_venta.payload_normalizado venta_id=%s payload=%s',
        venta.id,
        payload,
    )
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
            and _has_definitive_electronic_identifiers(factura_existente)
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
                    update_fields=[
                        'factura_electronica_uuid',
                        'factura_electronica_cufe',
                        'fecha_envio_dian',
                        'updated_at',
                    ]
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
            logger.info(
                'facturar_venta.reutiliza_en_proceso venta_id=%s numero=%s',
                venta.id,
                factura_existente.number,
            )
            return _sync_existing_pending_invoice(factura=factura_existente, venta=venta, triggered_by=triggered_by)
        if factura_existente and factura_existente.estado_electronico == 'PENDIENTE_REINTENTO' and force_resend_pending:
            logger.warning(
                'facturar_venta.reenvio_forzado_en_proceso venta_id=%s numero=%s',
                venta.id,
                factura_existente.number,
            )

        local_totals = _sync_sale_totals_before_emit(venta)
        payload = _build_and_log_factus_payload(venta)
        rango_activo = resolve_numbering_range(document_code='FACTURA_VENTA')
        _validate_customer_for_factus(payload.get('customer', {}), venta)
        _validate_payload_tax_consistency(payload, venta)
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
            # Reintentos con número ya asignado: resolver rango sin incrementar consecutivo.
            rango = resolve_numbering_range(document_code='FACTURA_VENTA')
            if not rango.factus_range_id:
                raise FactusValidationError(
                    'Debe sincronizar/configurar el rango antes de facturar. Falta factus_range_id del rango seleccionado.'
                )
            payload['numbering_range_id'] = int(rango.factus_range_id)

        should_lock_expected_number = _number_matches_active_range(numero, rango_activo.prefijo)
        if should_lock_expected_number:
            payload['number'] = numero
        else:
            payload.pop('number', None)
        reference_code = _resolve_reference_code(
            venta=venta,
            factura_existente=factura_existente,
            numero=numero,
        )
        payload['reference_code'] = reference_code
        if FacturaElectronica.objects.filter(reference_code=reference_code).exclude(venta=venta).exists():
            raise FacturaDuplicadaError(f'Ya existe una factura electrónica con reference_code={reference_code}.')

        factura, _ = FacturaElectronica.objects.update_or_create(
            venta=venta,
            defaults={
                'estado_electronico': 'PENDIENTE_REINTENTO',
                'number': numero,
                'reference_code': reference_code,
                'response_json': _build_attempt_trace(
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

    client = FactusClient()
    try:
        for index, item in enumerate(payload.get('items', []), start=1):
            if not isinstance(item, dict):
                continue
            logger.info(
                'facturar_venta.payload_pre_post_item venta_id=%s line=%s tax_rate=%s is_excluded=%s tribute_id=%s',
                venta.id,
                index,
                item.get('tax_rate'),
                item.get('is_excluded'),
                item.get('tribute_id'),
            )
        logger.info(
            'facturar_venta.payload_pre_post venta_id=%s payload=%s items=%s customer=%s payment_form=%s '
            'payment_method=%s numbering_range_id=%s operation_type=%s',
            venta.id,
            payload,
            payload.get('items', []),
            payload.get('customer', {}),
            payload.get('payment_form'),
            payload.get('payment_method_code'),
            payload.get('numbering_range_id'),
            payload.get('operation_type'),
        )
        response_json = client.create_and_validate_invoice(payload)
    except FactusPendingDianError as exc:
        logger.warning(
            'facturar_venta.factus_409_pendiente_dian venta_id=%s numero=%s reference_code=%s',
            venta.id,
            numero,
            reference_code,
        )
        _persist_pending_dian_conflict(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            error=exc,
        )
        return factura
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
        if isinstance(exc, FactusAPIError):
            rejection = str(getattr(exc, 'provider_detail', '') or '')
            if 'FAK21' in rejection:
                logger.warning(
                    'facturar_venta.rechazo_cliente_sin_id venta_id=%s cliente_id=%s numero=%s resumen=FAK21',
                    venta.id,
                    venta.cliente_id,
                    numero,
                )
        logger.warning('facturar_venta.factus_rechazo venta_id=%s numero=%s', venta.id, numero)
        raise
    logger.info('facturar_venta.factus_response venta_id=%s keys=%s', venta.id, sorted(response_json.keys()))

    fields = _extract_factus_data(response_json)
    fields['number'] = fields.get('number') or numero
    fields['reference_code'] = fields.get('reference_code') or reference_code
    pending_conciliation_error: FactusValidationError | None = None
    try:
        _assert_emitted_document_matches_sale(
            venta=venta,
            fields=fields,
            expected_number=numero if should_lock_expected_number else '',
            expected_reference_code=reference_code,
        )
    except FactusValidationError as exc:
        _persist_local_validation_error(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            error=exc,
            response=response_json,
        )
        raise
    try:
        _assert_document_conciliation(
            venta=venta,
            request_payload=payload,
            response_payload=response_json,
            logger_context=fields,
        )
    except FactusValidationError as exc:
        pending_conciliation_error = exc
    bill_errors = _extract_bill_errors(response_json)

    remote_snapshot_before = _extract_remote_document_snapshot(response_json)
    needs_conciliation_enrichment = not (
        remote_snapshot_before.get('total') is not None and remote_snapshot_before.get('customer_identification')
    )
    missing_before = [field for field in ['uuid', 'xml_url', 'pdf_url'] if not fields.get(field)]
    response_show_json: dict[str, Any] | None = None
    response_download_json: dict[str, Any] | None = None
    if missing_before or needs_conciliation_enrichment or pending_conciliation_error is not None:
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
        try:
            _assert_emitted_document_matches_sale(
                venta=venta,
                fields=fields,
                expected_number=numero if should_lock_expected_number else '',
                expected_reference_code=reference_code,
            )
            _assert_document_conciliation(
                venta=venta,
                request_payload=payload,
                response_payload=response_show_json,
                logger_context=fields,
            )
        except FactusValidationError as exc:
            _persist_local_validation_error(
                factura=factura,
                payload=payload,
                numero=numero,
                reference_code=reference_code,
                triggered_by=triggered_by,
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
                    venta.id,
                    fields['number'],
                    sorted(response_download_json.keys()),
                )
                fields = _merge_factus_fields(fields, _extract_factus_data(response_download_json))
                try:
                    _assert_emitted_document_matches_sale(
                        venta=venta,
                        fields=fields,
                        expected_number=numero if should_lock_expected_number else '',
                        expected_reference_code=reference_code,
                    )
                    _assert_document_conciliation(
                        venta=venta,
                        request_payload=payload,
                        response_payload=response_download_json,
                        logger_context=fields,
                    )
                except FactusValidationError as exc:
                    _persist_local_validation_error(
                        factura=factura,
                        payload=payload,
                        numero=numero,
                        reference_code=reference_code,
                        triggered_by=triggered_by,
                        error=exc,
                        response=response_json,
                        response_show=response_show_json,
                        response_download=response_download_json,
                    )
                    raise
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
    elif pending_conciliation_error is not None:
        _persist_local_validation_error(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            error=pending_conciliation_error,
            response=response_json,
        )
        raise pending_conciliation_error

    # Factus puede no devolver uuid/xml/pdf en validate; se completa con show/download
    # y, como último recurso, se genera URL directa de descarga para no abortar el flujo.
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
            factura,
            'response_json',
            _build_attempt_trace(
            factura=factura,
            payload=payload,
            numero=numero,
            reference_code=reference_code,
            triggered_by=triggered_by,
            status='ERROR_PERSISTENCIA',
            response=response_json,
            response_show=response_show_json,
            response_download=response_download_json,
            final_fields=fields,
            bill_errors=bill_errors,
            error={
                'message': 'Respuesta incompleta de Factus',
                'missing_fields': missing_fields,
            },
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
        raise FactusAPIError('La respuesta de Factus no contiene todos los datos requeridos.')

    persistable_fields = {k: v for k, v in fields.items() if k in PERSISTABLE_FACTURA_FIELDS}

    try:
        with transaction.atomic():
            factura = FacturaElectronica.objects.select_for_update().get(pk=factura.pk)
            for key, value in persistable_fields.items():
                if key == 'qr':
                    factura.qr_data = value
                elif key == 'qr_image':
                    _assign_qr_image_fields(factura, value)
                else:
                    if key in {'xml_url', 'pdf_url', 'public_url'}:
                        safe_assign_charfield(factura, key, value)
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
                factura,
                'response_json',
                _build_attempt_trace(
                factura=factura,
                payload=payload,
                numero=numero,
                reference_code=reference_code,
                triggered_by=triggered_by,
                status=persistable_fields.get('status', 'ERROR_INTEGRACION'),
                response=response_json,
                response_show=response_show_json,
                response_download=response_download_json,
                final_fields={**fields, 'persisted_fields': persistable_fields},
                bill_errors=bill_errors,
                ),
            )
            factura.observaciones_json = bill_errors
            factura.retry_count = int(factura.retry_count or 0) + 1
            factura.last_retry_at = timezone.now()
            factura.next_retry_at = None
            factura.ultima_sincronizacion_at = timezone.now()
            overflows = log_model_string_overflow_diagnostics(
                instance=factura, venta_id=venta.id, factura_id=factura.pk, stage='before_factura_save'
            )
            if overflows:
                raise FacturaPersistenciaError('Se detectaron campos con overflow antes de guardar la factura.')
            factura.save()

            incoming_uuid = fields.get('uuid') or ''
            incoming_cufe = fields.get('cufe') or ''
            if not venta.factura_electronica_uuid:
                venta.factura_electronica_uuid = incoming_uuid
            elif incoming_uuid and venta.factura_electronica_uuid != incoming_uuid:
                logger.warning(
                    'facturar_venta.no_sobrescribe_venta_uuid_historico venta_id=%s actual=%s incoming=%s',
                    venta.id,
                    venta.factura_electronica_uuid,
                    incoming_uuid,
                )
            if not venta.factura_electronica_cufe:
                venta.factura_electronica_cufe = incoming_cufe
            elif incoming_cufe and venta.factura_electronica_cufe != incoming_cufe:
                logger.warning(
                    'facturar_venta.no_sobrescribe_venta_cufe_historico venta_id=%s actual=%s incoming=%s',
                    venta.id,
                    venta.factura_electronica_cufe,
                    incoming_cufe,
                )
            venta.fecha_envio_dian = venta.fecha_envio_dian or factura.updated_at
            venta.save(update_fields=['factura_electronica_uuid', 'factura_electronica_cufe', 'fecha_envio_dian', 'updated_at'])
            logger.info(
                'facturar_venta.persistida venta_id=%s factura=%s status=%s reference_code=%s',
                venta.id,
                factura.number,
                factura.estado_electronico,
                factura.reference_code,
            )
            if factura.cufe and factura.number:
                qr_file = generate_qr_dian(factura.number, factura.cufe)
                factura.qr.save(qr_file.name, qr_file, save=False)
                factura.save(update_fields=['qr', 'updated_at'])
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
                instance=factura, venta_id=venta.id, factura_id=factura.pk, stage='dataerror_factura_save'
            )
            factura.save(update_fields=['estado_electronico', 'codigo_error', 'mensaje_error', 'updated_at'])
        raise DataError(str(exc))

    factura.send_email_enabled = bool(payload.get('send_email', True))
    factura.save(update_fields=['send_email_enabled', 'updated_at'])
    try:
        sync_invoice_assets(
            factura,
            include_email_content=not factura.send_email_enabled,
        )
    except DescargaFacturaError:
        logger.warning('facturar_venta.assets_sync_error venta_id=%s factura=%s', venta.id, factura.number, exc_info=True)
    logger.info(
        'facturar_venta.emitida_ok venta_id=%s factura_id=%s numero=%s estado=%s',
        venta.id,
        factura.pk,
        factura.number,
        factura.estado_electronico,
    )
    upload_custom_pdf_to_factus(factura)
    send_invoice_email_via_factus(factura)
    logger.info('facturar_venta.fin_ok venta_id=%s factura=%s', venta.id, factura.number)
    return factura
