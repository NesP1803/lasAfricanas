"""Builder único de payload para facturación electrónica Factus."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from apps.core.models import Impuesto
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.factus_catalog_lookup import (
    get_document_type_id,
    get_municipality_id,
    get_payment_method_code,
    get_tribute_id,
    get_unit_measure_id,
)
from apps.facturacion.services.factus_client import FactusValidationError
from apps.facturacion_electronica.catalogos.models import TributoFactus
from apps.ventas.models import Venta


def _to_float(value: Decimal) -> float:
    return float(value or Decimal('0'))


def _resolve_customer_tribute_id(tipo_documento: str) -> int:
    """Resuelve tribute_id de cliente según catálogo/homologación disponible."""
    doc = str(tipo_documento or '').strip().upper()
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


def build_invoice_payload(venta: Venta) -> dict:
    cliente = venta.cliente
    rango = resolve_numbering_range(document_code='FACTURA_VENTA')
    customer_tribute_id = _resolve_customer_tribute_id(cliente.tipo_documento)
    items = []
    for detalle in venta.detalles.select_related('producto').all():
        producto = detalle.producto
        items.append(
            {
                'code_reference': producto.codigo,
                'name': producto.nombre,
                'quantity': _to_float(detalle.cantidad),
                'price': _to_float(detalle.precio_unitario),
                'tax_rate': _to_float(detalle.iva_porcentaje),
                'unit_measure_id': get_unit_measure_id(producto.unidad_medida),
                'standard_code_id': 1,
                'tribute_id': _resolve_item_tribute_id(detalle.iva_porcentaje),
                'discount_rate': 0,
                'is_excluded': 1 if _to_float(detalle.iva_porcentaje) == 0 else 0,
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
        'customer': {
            'identification': cliente.numero_documento,
            'names': cliente.nombre,
            'email': cliente.email or 'no-email@example.com',
            'phone': cliente.telefono or '0000000000',
            'address': cliente.direccion or 'NO REGISTRADA',
            'municipality_id': get_municipality_id(cliente.ciudad or 'SIN_CIUDAD'),
            'identification_document_id': get_document_type_id(cliente.tipo_documento),
            'tribute_id': customer_tribute_id,
        },
        'items': items,
    }
