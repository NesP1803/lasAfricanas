from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from apps.facturacion.services.document_totals import calculate_document_detail_totals, q_money
from apps.facturacion.services.factus_client import FactusValidationError
from apps.facturacion.services.validators import to_bool, to_decimal_or_none
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)

MONEY_TOLERANCE = Decimal('0.05')
MONEY_QUANT = Decimal('0.01')
DOCUMENT_CONCILIATION_ERROR_CODE = 'ERROR_CONCILIACION_DOCUMENTAL'


def normalize_identification(value: Any) -> str:
    return ''.join(char for char in str(value or '').strip() if char.isalnum()).upper()


def quantize_money(value: Decimal | None) -> Decimal:
    normalized = Decimal(str(value if value is not None else '0'))
    return normalized.quantize(MONEY_QUANT)


def extract_request_document_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
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
        quantity = to_decimal_or_none(item.get('quantity')) or Decimal('0')
        unit_price = to_decimal_or_none(item.get('price')) or Decimal('0')
        discount_rate = to_decimal_or_none(item.get('discount_rate')) or Decimal('0')
        tax_rate = to_decimal_or_none(item.get('tax_rate')) or Decimal('0')
        is_excluded = to_bool(item.get('is_excluded'))

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
        'customer_identification': normalize_identification(
            customer.get('identification') or customer.get('identification_number') or customer.get('nit')
        ),
        'total': quantize_money(total),
        'tax_total': quantize_money(tax_total),
        'base_total': quantize_money(base_total),
        'items_count': len(items),
    }


def calculate_sale_document_totals_from_details(venta: Venta) -> dict[str, Decimal]:
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


def sync_sale_totals_before_emit(venta: Venta) -> dict[str, Decimal]:
    calculated = calculate_sale_document_totals_from_details(venta)
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


def extract_totals_from_items(items: list[Any]) -> dict[str, Decimal]:
    total = Decimal('0.00')
    tax_total = Decimal('0.00')
    base_total = Decimal('0.00')
    for item in items:
        if not isinstance(item, dict):
            continue
        quantity = to_decimal_or_none(item.get('quantity') or item.get('qty')) or Decimal('0')
        unit_price = to_decimal_or_none(
            item.get('price') or item.get('unit_price') or item.get('price_amount')
        ) or Decimal('0')
        discount_rate = to_decimal_or_none(
            item.get('discount_rate') or item.get('discount_percentage')
        ) or Decimal('0')
        discount_amount_field = to_decimal_or_none(
            item.get('discount_amount') or item.get('discount')
        ) or Decimal('0')
        tax_rate = to_decimal_or_none(item.get('tax_rate') or item.get('tax_percentage')) or Decimal('0')
        is_excluded = to_bool(item.get('is_excluded'))

        if discount_amount_field > Decimal('0.00'):
            gross_line = quantize_money(quantity * unit_price)
            discount_rate = quantize_money((discount_amount_field / gross_line) * Decimal('100')) if gross_line > Decimal('0.00') else Decimal('0.00')
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
        'total': quantize_money(total),
        'base_total': quantize_money(base_total),
        'tax_total': quantize_money(tax_total),
    }


def extract_remote_document_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
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

    tax_total = to_decimal_or_none(totals.get('tax_amount') or totals.get('tax') or totals.get('total_tax'))
    if tax_total is None:
        collected = [to_decimal_or_none((t.get('tax_amount') if isinstance(t, dict) else None)) for t in taxes]
        tax_total = sum((val for val in collected if val is not None), Decimal('0')) if collected else None
    items_totals = extract_totals_from_items(items)

    total_candidates = [
        to_decimal_or_none(totals.get('payable_amount')),
        to_decimal_or_none(totals.get('total_payable')),
        to_decimal_or_none(totals.get('total')),
        to_decimal_or_none(bill.get('total')),
        to_decimal_or_none(data.get('total')),
        items_totals['total'],
    ]
    base_candidates = [
        to_decimal_or_none(totals.get('taxable_amount')),
        to_decimal_or_none(totals.get('subtotal')),
        to_decimal_or_none(totals.get('line_extension_amount')),
        to_decimal_or_none(totals.get('gross_value')),
        to_decimal_or_none(bill.get('gross_value')),
        to_decimal_or_none(data.get('gross_value')),
        items_totals['base_total'],
    ]
    tax_candidates = [
        tax_total,
        items_totals['tax_total'],
    ]

    return {
        'customer_identification': normalize_identification(
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


def extract_items_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    bill = data.get('bill', data) if isinstance(data, dict) else {}
    items = bill.get('items', data.get('items', [])) if isinstance(bill, dict) else []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def is_remote_snapshot_inconclusive(*, remote: dict[str, Any], expected_tax: Decimal) -> bool:
    remote_tax = to_decimal_or_none(remote.get('tax_total'))
    remote_base = to_decimal_or_none(remote.get('base_total'))
    remote_total = to_decimal_or_none(remote.get('total'))
    items_count = int(remote.get('items_count') or 0)
    has_item_amounts = bool(remote.get('has_item_amounts'))
    tax_candidates = [v for v in (remote.get('tax_total_candidates') or []) if to_decimal_or_none(v) is not None]

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


def nearest_expected(candidates: list[Any], expected_value: Decimal) -> Decimal | None:
    normalized = [to_decimal_or_none(value) for value in candidates]
    valid = [value for value in normalized if value is not None]
    if not valid:
        return None
    return min(valid, key=lambda current: abs(current - expected_value))


def assert_document_conciliation(
    *,
    venta: Venta,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    logger_context: dict[str, Any],
) -> None:
    expected_snapshot = extract_request_document_snapshot(request_payload)
    expected = calculate_sale_document_totals_from_details(venta)
    remote = extract_remote_document_snapshot(response_payload)

    raw_local_total = to_decimal_or_none(venta.total) or Decimal('0')
    raw_local_tax = to_decimal_or_none(venta.iva) or Decimal('0')
    raw_local_base = to_decimal_or_none(venta.subtotal) or Decimal('0')

    expected_total = expected.get('total') or Decimal('0')
    expected_tax = expected.get('tax_total') or Decimal('0')
    expected_base = expected.get('base_total') or Decimal('0')
    expected_customer = normalize_identification(expected_snapshot.get('customer_identification') or '')
    expected_items_count = int(expected_snapshot.get('items_count') or 0)
    remote_is_inconclusive = is_remote_snapshot_inconclusive(remote=remote, expected_tax=expected_tax)

    mismatches: list[str] = []
    remote_total = nearest_expected(remote.get('total_candidates', []), expected_total) or remote.get('total')
    if (
        not remote_is_inconclusive
        and remote_total is not None
        and abs(remote_total - expected_total) > MONEY_TOLERANCE
    ):
        mismatches.append(f'total_remoto={remote_total} total_esperado={expected_total}')

    remote_tax = nearest_expected(remote.get('tax_total_candidates', []), expected_tax) or remote.get('tax_total')
    if (
        not remote_is_inconclusive
        and remote_tax is not None
        and abs(remote_tax - expected_tax) > MONEY_TOLERANCE
    ):
        mismatches.append(f'impuesto_remoto={remote_tax} impuesto_esperado={expected_tax}')

    remote_base = nearest_expected(remote.get('base_total_candidates', []), expected_base) or remote.get('base_total')
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
        request_items = extract_items_from_payload(request_payload)
        response_items = extract_items_from_payload(response_payload)
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
