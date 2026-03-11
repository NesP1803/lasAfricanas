"""Builder de payload para documento soporte electrónico Factus."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.facturacion.exceptions import DocumentoSoporteInvalido


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or '0'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise DocumentoSoporteInvalido('Valores numéricos inválidos en items del documento soporte.') from exc


def build_support_document_payload(data: dict[str, Any]) -> dict[str, Any]:
    proveedor_documento = str(data.get('proveedor_documento', '')).strip()
    if not proveedor_documento:
        raise DocumentoSoporteInvalido('El campo proveedor_documento es obligatorio.')

    items = data.get('items')
    if not isinstance(items, list) or not items:
        raise DocumentoSoporteInvalido('El campo items es obligatorio y debe contener al menos un elemento.')

    payload_items: list[dict[str, Any]] = []
    total = Decimal('0')
    for item in items:
        cantidad = _to_decimal(item.get('cantidad'))
        precio = _to_decimal(item.get('precio'))
        subtotal = cantidad * precio
        total += subtotal
        payload_items.append(
            {
                'name': str(item.get('descripcion', '')).strip() or 'Item',
                'quantity': float(cantidad),
                'price': float(precio),
            }
        )

    if total <= 0:
        raise DocumentoSoporteInvalido('El total del documento soporte debe ser mayor a 0.')

    return {
        'document': 'support_document',
        'supplier': {
            'name': str(data.get('proveedor_nombre', '')).strip(),
            'identification_number': proveedor_documento,
            'identification_type': str(data.get('proveedor_tipo_documento', 'CC')).strip() or 'CC',
        },
        'document_type': 'support_document',
        'payment_method': {'code': str(data.get('payment_method_code', '10')).strip() or '10'},
        'payment_method_code': str(data.get('payment_method_code', '10')).strip() or '10',
        'items': payload_items,
        'totals': {
            'subtotal': float(total),
            'total': float(total),
        },
    }
