"""Builder de payload para documento soporte electrónico Factus."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import logging
from typing import Any
import uuid

from apps.facturacion.exceptions import DocumentoSoporteInvalido
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.factus_catalog_lookup import (
    get_municipality_id,
    get_document_type_id,
    get_unit_measure_id,
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
    for index, item in enumerate(items, start=1):
        cantidad = _to_decimal(item.get('cantidad'))
        precio = _to_decimal(item.get('precio'))
        cantidad_entera = int(cantidad)
        if Decimal(cantidad_entera) != cantidad or cantidad_entera <= 0:
            raise DocumentoSoporteInvalido('La cantidad de cada ítem debe ser un entero positivo.')
        subtotal = cantidad * precio
        total += subtotal
        descripcion = str(item.get('descripcion', '')).strip() or f'Item {index}'
        payload_items.append(
            {
                'code_reference': str(item.get('codigo_referencia', f'DS-{index:03d}')).strip() or f'DS-{index:03d}',
                'name': descripcion,
                'quantity': cantidad_entera,
                'discount_rate': float(_to_decimal(item.get('descuento_porcentaje', 0))),
                'price': float(precio),
                'unit_measure_id': int(item.get('unit_measure_id') or get_unit_measure_id('94', default=70)),
                'standard_code_id': int(item.get('standard_code_id') or 1),
            }
        )

    if total <= 0:
        raise DocumentoSoporteInvalido('El total del documento soporte debe ser mayor a 0.')

    raw_tipo_documento = str(data.get('proveedor_tipo_documento', 'CC')).strip() or 'CC'
    proveedor_tipo_documento = normalize_document_type_code(raw_tipo_documento)
    identification_default = 6 if proveedor_tipo_documento == 'NIT' else 3
    identification_document_id = get_document_type_id(
        proveedor_tipo_documento,
        default=identification_default,
        seed_if_missing=True,
    )
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

    reference_code = str(data.get('reference_code', '')).strip() or f'DSREF-{uuid.uuid4().hex[:12].upper()}'

    try:
        numbering_range = resolve_numbering_range(document_code='DOCUMENTO_SOPORTE')
        numbering_range_id = int(numbering_range.factus_range_id or numbering_range.factus_id or 0)
    except Exception as exc:
        raise DocumentoSoporteInvalido(str(exc)) from exc
    if not numbering_range_id:
        raise DocumentoSoporteInvalido('El rango activo de documento soporte no tiene factus_range_id válido.')

    provider_address = str(data.get('provider_address') or '').strip() or 'NA'
    provider_email = str(data.get('provider_email') or '').strip() or 'no-email@no-email.com'
    provider_phone = str(data.get('provider_phone') or '').strip()
    provider_country_code = str(data.get('provider_country_code') or 'CO').strip().upper() or 'CO'
    provider_municipality_id = data.get('provider_municipality_id')
    if provider_country_code == 'CO':
        if provider_municipality_id in (None, ''):
            provider_municipality_id = get_municipality_id(str(data.get('provider_city') or '47001'), default=149)
        provider_municipality_id = int(provider_municipality_id)

    provider_payload: dict[str, Any] = {
        'identification_document_id': identification_document_id,
        'identification': proveedor_documento,
        'dv': int(data.get('provider_dv') or 0) if proveedor_tipo_documento == 'NIT' and str(data.get('provider_dv') or '').strip() else None,
        'trade_name': str(data.get('provider_trade_name') or '').strip(),
        'names': str(data.get('proveedor_nombre', '')).strip(),
        'address': provider_address,
        'email': provider_email,
        'phone': provider_phone,
        'is_resident': int(data.get('provider_is_resident', 1)),
        'country_code': provider_country_code,
        'municipality_id': provider_municipality_id if provider_country_code == 'CO' else None,
    }
    provider_payload = {k: v for k, v in provider_payload.items() if v not in (None, '')}

    return {
        'reference_code': reference_code,
        'numbering_range_id': numbering_range_id,
        'payment_method_code': str(data.get('payment_method_code', '10')).strip() or '10',
        'observation': str(data.get('observation', '')).strip()[:250],
        'provider': provider_payload,
        'items': payload_items,
    }
