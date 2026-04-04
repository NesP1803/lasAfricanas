"""Helpers de cálculo documental para facturación electrónica."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


CENT = Decimal('0.01')
HUNDRED = Decimal('100')


def to_decimal(value: Any, default: str = '0') -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def q_money(value: Decimal | Any) -> Decimal:
    return Decimal(str(value if value is not None else '0')).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_document_detail_totals(
    *,
    quantity: Any,
    unit_gross_price: Any,
    discount_pct: Any,
    tax_pct: Any,
) -> dict[str, Decimal]:
    qty = to_decimal(quantity)
    unit_price = to_decimal(unit_gross_price)
    discount_rate = max(Decimal('0.00'), to_decimal(discount_pct))
    vat_rate = max(Decimal('0.00'), to_decimal(tax_pct))

    total_bruto = q_money(qty * unit_price)
    descuento_valor = q_money((total_bruto * discount_rate) / HUNDRED)
    if descuento_valor > total_bruto:
        descuento_valor = total_bruto
    total = q_money(total_bruto - descuento_valor)

    if vat_rate <= Decimal('0.00'):
        base = total
        impuesto = Decimal('0.00')
    else:
        divisor = Decimal('1.00') + (vat_rate / HUNDRED)
        base = q_money(total / divisor)
        impuesto = q_money(total - base)

    return {
        'total_bruto': total_bruto,
        'descuento_valor': descuento_valor,
        'base': base,
        'impuesto': impuesto,
        'total': total,
    }


def unit_base_without_tax(*, unit_final_price: Any, tax_rate: Any, is_excluded: bool) -> Decimal:
    unit_final = to_decimal(unit_final_price)
    rate = to_decimal(tax_rate)
    if is_excluded or rate <= Decimal('0'):
        return q_money(unit_final)
    divisor = Decimal('1') + (rate / HUNDRED)
    return q_money(unit_final / divisor)


def line_base_total(*, quantity: Any, unit_base: Any) -> Decimal:
    return q_money(to_decimal(quantity) * to_decimal(unit_base))


def line_tax_total(*, line_total: Any, line_base: Any, is_excluded: bool, tax_rate: Any) -> Decimal:
    if is_excluded or to_decimal(tax_rate) <= Decimal('0'):
        return Decimal('0.00')
    return q_money(to_decimal(line_total) - to_decimal(line_base))


def line_total(*, quantity: Any, unit_final_price: Any, discount_total: Any = 0) -> Decimal:
    gross = q_money(to_decimal(quantity) * to_decimal(unit_final_price))
    discount = q_money(min(gross, max(Decimal('0.00'), to_decimal(discount_total))))
    return q_money(gross - discount)
