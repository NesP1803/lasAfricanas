"""Builder único de payload para facturación electrónica Factus."""

from __future__ import annotations

from decimal import Decimal
import re
import logging

from django.conf import settings

from apps.core.models import Impuesto
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.factus_catalog_lookup import (
    get_document_type_id,
    get_municipality_id,
    get_payment_method_code,
    get_tribute_id,
    get_unit_measure_id,
    normalize_document_type_code,
)
from apps.facturacion.services.factus_client import FactusValidationError
from apps.facturacion_electronica.catalogos.models import TributoFactus
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def _to_float(value: Decimal) -> float:
    return float(value or Decimal('0'))


def _to_decimal(value, default: str = '0') -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


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

    fallback = (
        TributoFactus.objects.filter(is_active=True)
        .order_by('factus_id')
        .values_list('factus_id', flat=True)
        .first()
    )
    return int(fallback or 1)


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
    producto = detalle.producto
    iva_porcentaje = _to_decimal(detalle.iva_porcentaje)
    return bool(getattr(producto, 'iva_exento', False) or iva_porcentaje <= Decimal('0'))


def _resolve_item_unit_price(detalle) -> Decimal:
    cantidad = _to_decimal(detalle.cantidad)
    if cantidad <= Decimal('0'):
        raise FactusValidationError('La cantidad del item debe ser mayor a cero para facturación electrónica.')
    total_linea = _to_decimal(detalle.total)
    if total_linea <= Decimal('0'):
        precio_unitario = _to_decimal(detalle.precio_unitario)
        descuento_unitario = _to_decimal(detalle.descuento_unitario)
        total_linea = max(Decimal('0'), (precio_unitario - descuento_unitario) * cantidad)
    return total_linea / cantidad


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
    rango = resolve_numbering_range(document_code='FACTURA_VENTA')
    items = []
    for detalle in venta.detalles.select_related('producto').all():
        producto = detalle.producto
        is_excluded = _is_excluded_item(detalle)
        tax_rate = Decimal('0.00') if is_excluded else _to_decimal(detalle.iva_porcentaje)
        tribute_id = (
            _resolve_excluded_item_tribute_id()
            if is_excluded
            else _resolve_item_tribute_id(tax_rate)
        )
        items.append(
            {
                'code_reference': producto.codigo,
                'name': producto.nombre,
                'quantity': _to_float(detalle.cantidad),
                'price': _to_float(_resolve_item_unit_price(detalle)),
                'tax_rate': _to_float(tax_rate),
                'unit_measure_id': get_unit_measure_id(producto.unidad_medida),
                'standard_code_id': 1,
                'tribute_id': tribute_id,
                'discount_rate': 0,
                'is_excluded': 1 if is_excluded else 0,
            }
        )

    return {
        'document': '01',
        'numbering_range_id': int(rango.factus_range_id or settings.FACTUS_NUMBERING_RANGE_FACTURA),
        'reference_code': venta.numero_comprobante,
        'observation': venta.observaciones or '',
        'payment_form': '1',
        'payment_method_code': get_payment_method_code(venta.medio_pago),
        'operation_type': settings.FACTUS_OPERATION_TYPE,
        'send_email': settings.FACTUS_SEND_EMAIL_DEFAULT,
        'customer': _build_customer_payload(cliente),
        'items': items,
    }
