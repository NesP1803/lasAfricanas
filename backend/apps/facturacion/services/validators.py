from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.factus_catalog_lookup import get_tribute_id
from apps.facturacion.services.factus_client import FactusValidationError
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'si', 'sí', 'yes', 'y', 'on'}


def has_definitive_electronic_identifiers(factura: FacturaElectronica | None) -> bool:
    if factura is None:
        return False
    return bool(
        str(factura.uuid or '').strip()
        and str(factura.cufe or '').strip()
        and str(factura.number or '').strip()
    )


def number_matches_active_range(numero: str, prefijo_rango: str) -> bool:
    numero_normalizado = str(numero or '').strip().upper()
    prefijo_normalizado = str(prefijo_rango or '').strip().upper()
    if not numero_normalizado or not prefijo_normalizado:
        return False
    return numero_normalizado.startswith(prefijo_normalizado)


def validate_customer_for_factus(customer: dict[str, Any], venta: Venta) -> None:
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


def validate_payload_tax_consistency(payload: dict[str, Any], venta: Venta) -> None:
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
        is_excluded = to_bool(item.get('is_excluded'))
        tax_rate = to_decimal_or_none(item.get('tax_rate')) or Decimal('0.00')
        taxable_amount = to_decimal_or_none(item.get('taxable_amount')) or Decimal('0.00')
        tax_amount = to_decimal_or_none(item.get('tax_amount')) or Decimal('0.00')
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
