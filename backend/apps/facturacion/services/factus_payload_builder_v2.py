"""Helpers de payload Factus API v2 (compatibles con transición desde v1)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def _q2(value: Decimal) -> Decimal:
    return (value or Decimal('0')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def build_v2_payment_details(*, payment_form: str, payment_method_code: str, amount: Decimal | int | float, reference_code: str = '', due_date: str | None = None) -> list[dict[str, str]]:
    payload = {
        'payment_form': str(payment_form),
        'payment_method_code': str(payment_method_code),
        'reference_code': str(reference_code or ''),
        'amount': f"{_q2(Decimal(str(amount))):.2f}",
    }
    if due_date:
        payload['due_date'] = due_date
    return [payload]


def gross_to_net_price(unit_gross_price: Decimal | int | float, tax_rate_percent: Decimal | int | float) -> Decimal:
    gross = Decimal(str(unit_gross_price))
    rate = Decimal(str(tax_rate_percent))
    if rate <= Decimal('0'):
        return _q2(gross)
    return _q2(gross / (Decimal('1') + (rate / Decimal('100'))))


def build_v2_item_taxes(tax_rate_percent: Decimal | int | float) -> list[dict[str, str | bool]]:
    rate = Decimal(str(tax_rate_percent))
    if rate <= Decimal('0'):
        return [{'is_excluded': True}]
    return [{'code': '01', 'rate': f'{_q2(rate):.2f}'}]
