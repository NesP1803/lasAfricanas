"""Builder de payload para documento soporte electrónico Factus."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import logging
from typing import Any

from apps.facturacion.exceptions import DocumentoSoporteInvalido
from apps.facturacion.services.factus_catalog_lookup import (
    get_document_type_id,
    get_payment_method_code,
    normalize_document_type_code,
)

logger = logging.getLogger(__name__)


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

    raw_tipo_documento = str(data.get('proveedor_tipo_documento', 'CC')).strip() or 'CC'
    proveedor_tipo_documento = normalize_document_type_code(raw_tipo_documento)
    identification_document_id = get_document_type_id(proveedor_tipo_documento, default=0, seed_if_missing=True)
    if not identification_document_id:
        logger.warning(
            'factus_payload.support_document_invalid reason=document_type_not_homologated '
            'tipo_documento_raw=%s tipo_documento_normalized=%s proveedor_documento=%s',
            raw_tipo_documento,
            proveedor_tipo_documento,
            proveedor_documento,
        )
        raise DocumentoSoporteInvalido(
            f"El tipo de documento del proveedor '{proveedor_tipo_documento}' no está homologado para Factus."
        )

    payment_method_code = get_payment_method_code(str(data.get('payment_method_code', '10')).strip(), default='')
    if not payment_method_code:
        raise DocumentoSoporteInvalido(
            'El método de pago del documento soporte no está homologado para Factus.'
        )

    return {
        'document': 'support_document',
        'supplier': {
            'name': str(data.get('proveedor_nombre', '')).strip(),
            'identification_number': proveedor_documento,
            'identification_type': proveedor_tipo_documento,
            'identification_document_id': identification_document_id,
        },
        'document_type': 'support_document',
        'payment_method': {'code': payment_method_code},
        'payment_method_code': payment_method_code,
        'items': payload_items,
        'totals': {
            'subtotal': float(total),
            'total': float(total),
        },
    }
