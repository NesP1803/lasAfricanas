from decimal import Decimal

from django.conf import settings

from apps.facturacion_electronica.selectors import (
    get_municipality_id,
    get_payment_method_code,
    get_tribute_id,
    get_unit_measure_id,
)


def _decimal_to_float(value: Decimal) -> float:
    return float(value or Decimal('0'))


def get_identification_document_id(tipo_documento: str) -> int:
    mapping = {
        'CC': 3,
        'NIT': 6,
        'CE': 5,
        'PAS': 7,
        'TI': 4,
    }
    return mapping.get(tipo_documento, 3)


def build_payload_from_venta(venta):
    cliente = venta.cliente
    customer = {
        'identification': cliente.numero_documento,
        'names': cliente.nombre,
        'email': cliente.email or 'no-email@example.com',
        'phone': cliente.telefono or '0000000000',
        'municipality_id': get_municipality_id(cliente.ciudad or 'SIN_CIUDAD'),
        'identification_document_id': get_identification_document_id(cliente.tipo_documento),
        # TODO: reemplazar por `cliente.responsabilidad_fiscal` cuando esté disponible en el modelo.
        'tribute_id': get_tribute_id('IVA'),
    }

    items = []
    for detalle in venta.detalles.select_related('producto').all():
        producto = detalle.producto
        items.append(
            {
                'code_reference': producto.codigo,
                'name': producto.nombre,
                'quantity': _decimal_to_float(detalle.cantidad),
                'price': _decimal_to_float(detalle.precio_unitario),
                'tax_rate': _decimal_to_float(detalle.iva_porcentaje),
                'unit_measure_id': get_unit_measure_id(producto.unidad_medida),
                'standard_code_id': 1,
                'tribute_id': get_tribute_id('IVA'),
                'is_excluded': _decimal_to_float(detalle.iva_porcentaje) == 0,
            }
        )

    payload = {
        'document': '01',
        'numbering_range_id': settings.FACTUS_NUMBERING_RANGE_FACTURA,
        'reference_code': venta.numero_comprobante,
        'payment_method_code': get_payment_method_code(venta.medio_pago),
        'customer': customer,
        'items': items,
    }

    return payload
