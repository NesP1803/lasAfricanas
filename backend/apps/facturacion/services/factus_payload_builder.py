"""Builder único de payload para facturación electrónica Factus."""

from __future__ import annotations

from decimal import Decimal
import re
import logging
from typing import Any

from django.conf import settings

from apps.core.models import ConfiguracionFacturacion, Impuesto
from apps.facturacion.services.consecutivo_service import resolve_electronic_numbering_range_id
from apps.facturacion.services.factus_catalog_lookup import (
    get_first_active_tribute_id,
    get_document_type_id,
    get_municipality_id,
    get_payment_method_code,
    get_tribute_id,
    get_unit_measure_id,
    normalize_document_type_code,
)
from apps.facturacion.services.factus_client import FactusValidationError
from apps.facturacion.services.document_totals import (
    calculate_document_detail_totals,
    q_money,
    to_decimal,
)
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)
HUNDRED = Decimal('100.00')


def _to_float(value: Decimal) -> float:
    return float(value or Decimal('0'))


def _to_clean_text(value: Any, *, fallback: str) -> str:
    text = str(value or '').strip()
    return text or fallback


def _resolve_customer_tribute_id(tipo_documento: str) -> int:
    """Resuelve tribute_id de cliente según catálogo/homologación disponible."""
    doc = normalize_document_type_code(tipo_documento)
    if doc != 'NIT':
        return 21
    preferred_codes = ['R-99-PN', 'R-99', 'NO_CAUSA']
    if doc == 'NIT':
        preferred_codes = ['IVA', '01', 'R-99-PN']

    for code in preferred_codes:
        tribute_id = get_tribute_id(code, default=0)
        if tribute_id:
            return int(tribute_id)

    return get_first_active_tribute_id(default=1)


def _resolve_item_tribute_id(iva_porcentaje: Decimal) -> int:
    porcentaje = Decimal(iva_porcentaje or Decimal('0'))
    impuesto = (
        Impuesto.objects.filter(porcentaje=porcentaje, is_active=True)
        .exclude(factus_tribute_id__isnull=True)
        .order_by('-id')
        .first()
    )
    if not impuesto or not impuesto.factus_tribute_id:
        raise FactusValidationError(
            f'Falta homologación Factus para impuesto {porcentaje}% en Configuración > Impuestos.'
        )
    return int(impuesto.factus_tribute_id)


def _resolve_excluded_item_tribute_id() -> int:
    return int(get_tribute_id('NO_CAUSA', default=1))


def _is_excluded_item(detalle) -> bool:
    iva_porcentaje = q_money(to_decimal(detalle.iva_porcentaje))
    return iva_porcentaje <= Decimal('0.00')


def _resolve_item_unit_gross_price(detalle) -> Decimal:
    cantidad = to_decimal(detalle.cantidad)
    if cantidad <= Decimal('0'):
        raise FactusValidationError('La cantidad del item debe ser mayor a cero para facturación electrónica.')
    precio_unitario = to_decimal(detalle.precio_unitario)
    if precio_unitario < Decimal('0'):
        raise FactusValidationError('El precio unitario del item no puede ser negativo.')
    return q_money(precio_unitario)


def _line_gross_total(detalle) -> Decimal:
    cantidad = to_decimal(detalle.cantidad)
    unit_price = _resolve_item_unit_gross_price(detalle)
    return q_money(cantidad * unit_price)


def _line_own_discount_total(detalle) -> Decimal:
    cantidad = to_decimal(detalle.cantidad)
    descuento_unitario = max(to_decimal(detalle.descuento_unitario), Decimal('0'))
    gross_total = _line_gross_total(detalle)
    return min(gross_total, q_money(cantidad * descuento_unitario))


def _resolve_item_discount_rate(detalle) -> Decimal:
    gross_total = _line_gross_total(detalle)
    if gross_total <= Decimal('0.00'):
        return Decimal('0.00')

    own_discount = _line_own_discount_total(detalle)
    total_discount = min(
        gross_total,
        q_money(own_discount),
    )
    if total_discount <= Decimal('0.00'):
        return Decimal('0.00')

    discount_rate = q_money((total_discount / gross_total) * HUNDRED)
    return min(HUNDRED, max(Decimal('0.00'), discount_rate))


def _normalize_document_detail(detalle) -> dict[str, Any]:
    """
    Normaliza una línea documental local en una única fuente de verdad.

    Esta estructura evita recalcular cantidades/base/impuesto/total en
    múltiples capas y deja explícita la semántica antes de mapear a Factus.
    """
    producto = detalle.producto
    quantity = q_money(to_decimal(detalle.cantidad))
    if quantity <= Decimal('0.00'):
        raise FactusValidationError('La cantidad del item debe ser mayor a cero para facturación electrónica.')

    unit_gross_price = _resolve_item_unit_gross_price(detalle)
    discount_rate = _resolve_item_discount_rate(detalle)
    iva_porcentaje = q_money(to_decimal(detalle.iva_porcentaje))
    is_excluded = _is_excluded_item(detalle)
    tax_rate = Decimal('0.00') if is_excluded else iva_porcentaje
    tribute_id = _resolve_excluded_item_tribute_id() if is_excluded else _resolve_item_tribute_id(tax_rate)

    totals = calculate_document_detail_totals(
        quantity=quantity,
        unit_gross_price=unit_gross_price,
        discount_pct=discount_rate,
        tax_pct=tax_rate,
    )
    normalized_detail = {
        'code_reference': _to_clean_text(getattr(producto, 'codigo', ''), fallback=str(detalle.id)),
        'name': _to_clean_text(getattr(producto, 'nombre', ''), fallback=f'ITEM-{detalle.id}'),
        'quantity': quantity,
        'unit_gross_price': unit_gross_price,
        'discount_rate': discount_rate,
        'tax_rate': tax_rate,
        'is_excluded': is_excluded,
        'tribute_id': int(tribute_id),
        'unit_measure_id': int(get_unit_measure_id(producto.unidad_medida)),
        'standard_code_id': 1,
        'withholding_taxes': [],
        'totals': totals,
    }
    logger.info(
        'factus_payload.item_normalized code_reference=%s iva_porcentaje_detalle=%s tax_rate=%s is_excluded=%s tribute_id=%s',
        normalized_detail['code_reference'],
        iva_porcentaje,
        normalized_detail['tax_rate'],
        normalized_detail['is_excluded'],
        normalized_detail['tribute_id'],
    )
    return normalized_detail


def build_factus_item(document_detail: dict[str, Any]) -> dict[str, Any]:
    """
    Traduce una línea documental local al formato Factus.

    Convención elegida por compatibilidad con Factus:
    - `price` se envía como precio unitario final (con IVA cuando aplique), como espera Factus.
    - Para líneas gravadas, `tax_rate` > 0, `is_excluded`=False y `tribute_id` de IVA.
    """
    is_excluded = bool(document_detail['is_excluded'])
    tax_rate = q_money(to_decimal(document_detail.get('tax_rate')))
    tribute_id = int(document_detail.get('tribute_id') or 0)
    excluded_tribute_id = _resolve_excluded_item_tribute_id()

    if is_excluded and tax_rate > Decimal('0.00'):
        raise FactusValidationError('Una línea excluida debe enviarse con tax_rate igual a 0.')
    if not is_excluded and tax_rate <= Decimal('0.00'):
        raise FactusValidationError('Una línea gravada debe enviarse con tax_rate mayor a 0.')
    if not is_excluded and tribute_id <= 0:
        raise FactusValidationError('Una línea gravada debe enviarse con tribute_id válido.')
    if is_excluded and tribute_id != excluded_tribute_id:
        raise FactusValidationError(
            f'Una línea excluida debe enviarse con tribute_id={excluded_tribute_id} (no causa/excluido).'
        )

    effective_tax_rate = Decimal('0.00') if is_excluded else tax_rate
    price_for_factus = q_money(document_detail['unit_gross_price'])
    totals = document_detail.get('totals', {}) if isinstance(document_detail.get('totals'), dict) else {}
    taxable_amount = q_money(to_decimal(totals.get('base', Decimal('0.00'))))
    tax_amount = q_money(to_decimal(totals.get('impuesto', Decimal('0.00'))))
    line_total = q_money(to_decimal(totals.get('total', Decimal('0.00'))))
    if is_excluded:
        taxable_amount = Decimal('0.00')
        tax_amount = Decimal('0.00')
    elif taxable_amount <= Decimal('0.00') or tax_amount <= Decimal('0.00'):
        raise FactusValidationError('Una línea gravada debe tener taxable_amount y tax_amount mayores a 0.')

    item_payload = {
        'code_reference': document_detail['code_reference'],
        'name': document_detail['name'],
        'quantity': _to_float(document_detail['quantity']),
        'price': _to_float(price_for_factus),
        'tax_rate': _to_float(effective_tax_rate),
        'taxable_amount': _to_float(taxable_amount),
        'tax_amount': _to_float(tax_amount),
        'total': _to_float(line_total),
        'discount_rate': _to_float(document_detail['discount_rate']),
        'is_excluded': int(1 if is_excluded else 0),
        'tribute_id': tribute_id,
        'unit_measure_id': int(document_detail['unit_measure_id']),
        'standard_code_id': int(document_detail['standard_code_id']),
        'withholding_taxes': document_detail.get('withholding_taxes', []),
    }
    logger.info(
        'factus_payload.item_built payload=%s is_excluded_type=%s',
        item_payload,
        type(item_payload['is_excluded']).__name__,
    )
    return item_payload


def _normalize_identification(value: str) -> str:
    raw = str(value or '').strip()
    # Factus espera el identificador del adquiriente sin separadores visibles.
    return re.sub(r'[^0-9A-Za-z]', '', raw)


def _build_customer_payload(cliente) -> dict:
    identification = _normalize_identification(cliente.numero_documento)
    names = str(cliente.nombre or '').strip()
    raw_tipo_documento = str(getattr(cliente, 'tipo_documento', '') or '')
    tipo_documento = normalize_document_type_code(raw_tipo_documento)

    if not identification:
        logger.warning(
            'factus_payload.customer_invalid cliente_id=%s reason=missing_identification tipo_documento_raw=%s',
            getattr(cliente, 'id', None),
            raw_tipo_documento,
        )
        raise FactusValidationError(
            'El cliente seleccionado no tiene número de identificación configurado para facturación electrónica.'
        )
    if not names:
        logger.warning(
            'factus_payload.customer_invalid cliente_id=%s reason=missing_names tipo_documento_raw=%s',
            getattr(cliente, 'id', None),
            raw_tipo_documento,
        )
        raise FactusValidationError(
            'El cliente seleccionado no tiene nombre o razón social configurado para facturación electrónica.'
        )
    if not tipo_documento:
        logger.warning(
            'factus_payload.customer_invalid cliente_id=%s reason=missing_document_type identification=%s',
            getattr(cliente, 'id', None),
            identification,
        )
        raise FactusValidationError('El cliente seleccionado no tiene tipo de documento configurado.')

    generic_names = {'CLIENTE GENERAL', 'CONSUMIDOR FINAL', 'PUBLICO GENERAL'}
    generic_docs = {'0', '1', '9', '222222', '222222222', '222222222222', '999999', '999999999'}
    if names.strip().upper() in generic_names and identification in generic_docs:
        logger.warning(
            'factus_payload.customer_invalid cliente_id=%s reason=generic_customer_not_allowed '
            'identification=%s tipo_documento=%s',
            getattr(cliente, 'id', None),
            identification,
            tipo_documento,
        )
        raise FactusValidationError(
            'El cliente general no puede usarse para facturación electrónica sin identificación fiscal válida.'
        )

    identification_document_id = get_document_type_id(tipo_documento, default=0)
    if not identification_document_id:
        identification_document_id = get_document_type_id(tipo_documento, default=0, seed_if_missing=True)
    if not identification_document_id:
        logger.warning(
            'factus_payload.customer_invalid cliente_id=%s reason=document_type_not_homologated '
            'tipo_documento_raw=%s tipo_documento_normalized=%s',
            getattr(cliente, 'id', None),
            raw_tipo_documento,
            tipo_documento,
        )
        raise FactusValidationError(
            f"El tipo de documento '{tipo_documento}' no está homologado para Factus."
        )
    logger.info(
        'factus_payload.customer_document_homologation cliente_id=%s tipo_documento_raw=%s '
        'tipo_documento_normalized=%s identification_document_id=%s',
        getattr(cliente, 'id', None),
        raw_tipo_documento,
        tipo_documento,
        identification_document_id,
    )

    return {
        'identification': identification,
        'names': names,
        'email': cliente.email or 'no-email@example.com',
        'phone': cliente.telefono or '0000000000',
        'address': cliente.direccion or 'NO REGISTRADA',
        'municipality_id': get_municipality_id(cliente.ciudad or 'SIN_CIUDAD', default=149),
        'identification_document_id': identification_document_id,
        'tribute_id': _resolve_customer_tribute_id(tipo_documento),
    }


def build_invoice_payload(venta: Venta) -> dict:
    cliente = venta.cliente
    numbering_range_id = resolve_electronic_numbering_range_id(document_code='FACTURA_VENTA')
    logger.info(
        'factus_payload.invoice.range_resolved venta_id=%s numbering_range_id=%s',
        venta.id,
        numbering_range_id,
    )
    configuracion = ConfiguracionFacturacion.objects.order_by('-id').first()
    detalles = list(venta.detalles.select_related('producto').all())
    items: list[dict[str, Any]] = []
    for detalle in detalles:
        normalized_line = _normalize_document_detail(detalle)
        doc_line = normalized_line['totals']
        logger.info(
            'factus_payload.item code=%s qty=%s price_gross=%s tax_rate=%s is_excluded=%s discount_pct=%s '
            'base=%s tax=%s total=%s',
            normalized_line['code_reference'],
            normalized_line['quantity'],
            normalized_line['unit_gross_price'],
            normalized_line['tax_rate'],
            1 if normalized_line['is_excluded'] else 0,
            normalized_line['discount_rate'],
            doc_line['base'],
            doc_line['impuesto'],
            doc_line['total'],
        )
        items.append(build_factus_item(normalized_line))

    payload = {
        'document': '01',
        'numbering_range_id': numbering_range_id,
        'observation': venta.observaciones or '',
        'payment_form': '1',
        'payment_method_code': get_payment_method_code(venta.medio_pago),
        'operation_type': settings.FACTUS_OPERATION_TYPE,
        'send_email': settings.FACTUS_SEND_EMAIL_DEFAULT,
        'customer': _build_customer_payload(cliente),
        'items': items,
    }
    if configuracion and configuracion.prefijo_factura_electronica:
        payload['prefix'] = str(configuracion.prefijo_factura_electronica).strip()
    logger.info('factus_payload.final payload=%s', payload)
    return payload
