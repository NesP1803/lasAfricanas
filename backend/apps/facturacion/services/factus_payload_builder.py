"""Builder único de payload para facturación electrónica Factus."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from apps.facturacion.services.factus_catalog_lookup import (
    get_document_type_id,
    get_municipality_id,
    get_payment_method_code,
    get_tribute_id,
    get_unit_measure_id,
)
from apps.ventas.models import Venta


def _to_float(value: Decimal) -> float:
    return float(value or Decimal('0'))


def build_invoice_payload(venta: Venta) -> dict:
    cliente = venta.cliente
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
                'tribute_id': get_tribute_id('IVA'),
                'is_excluded': _to_float(detalle.iva_porcentaje) == 0,
            }
        )

    return {
        'document': '01',
        'numbering_range_id': settings.FACTUS_NUMBERING_RANGE_FACTURA,
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
            'tribute_id': get_tribute_id('IVA'),
        },
        'items': items,
    }
