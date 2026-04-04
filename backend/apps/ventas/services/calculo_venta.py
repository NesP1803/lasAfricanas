from __future__ import annotations

from decimal import Decimal

from apps.facturacion.services.document_totals import calculate_document_detail_totals, q_money
CENT = Decimal('0.01')


def to_decimal(value, default='0'):
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def q(value):
    return q_money(value)


def detalle_es_exento(detalle, iva_porcentaje):
    producto = detalle.get('producto')
    if producto is not None and getattr(producto, 'iva_exento', False):
        return True
    return iva_porcentaje <= Decimal('0')


def calcular_detalle_venta(detalle):
    """
    Convención de dominio:
    - precio_unitario SIEMPRE representa precio final unitario (incluye IVA cuando aplica).
    - total de línea = cantidad * precio_unitario - descuentos por línea.
    - subtotal de línea = base sin IVA (o total de línea si es exento/no gravado).
    - iva de línea = total de línea - subtotal de línea.
    """
    cantidad = to_decimal(detalle.get('cantidad'))
    precio_unitario = to_decimal(detalle.get('precio_unitario'))
    descuento_unitario = to_decimal(detalle.get('descuento_unitario', 0))
    iva_porcentaje = to_decimal(detalle.get('iva_porcentaje', 0))

    total_bruto_linea = q(cantidad * precio_unitario)
    descuento_linea = q(min(total_bruto_linea, cantidad * max(descuento_unitario, Decimal('0'))))
    descuento_pct = Decimal('0.00')
    if total_bruto_linea > Decimal('0.00'):
        descuento_pct = q((descuento_linea / total_bruto_linea) * Decimal('100'))
    tax_pct = Decimal('0.00') if detalle_es_exento(detalle, iva_porcentaje) else iva_porcentaje
    calculo_doc = calculate_document_detail_totals(
        quantity=cantidad,
        unit_gross_price=precio_unitario,
        discount_pct=descuento_pct,
        tax_pct=tax_pct,
    )
    total_neto_linea_q = calculo_doc['total']
    base_linea_q = calculo_doc['base']
    iva_linea_q = calculo_doc['impuesto']

    detalle['subtotal'] = base_linea_q
    detalle['total'] = total_neto_linea_q

    return {
        'base_linea': base_linea_q,
        'iva_linea': iva_linea_q,
        'total_linea': total_neto_linea_q,
    }


def recalcular_totales_venta(detalles_data, descuento_porcentaje=0, descuento_valor=0, efectivo_recibido=None):
    subtotal = Decimal('0.00')
    iva = Decimal('0.00')
    total_detalles = Decimal('0.00')

    for detalle in detalles_data:
        calculo = calcular_detalle_venta(detalle)
        subtotal += calculo['base_linea']
        iva += calculo['iva_linea']
        total_detalles += calculo['total_linea']

    descuento_porcentaje = max(Decimal('0.00'), to_decimal(descuento_porcentaje))
    descuento_valor = max(Decimal('0.00'), to_decimal(descuento_valor))
    if descuento_porcentaje > Decimal('0.00') or descuento_valor > Decimal('0.00'):
        # El descuento documental ya se refleja por detalle (descuento_unitario).
        # Se conserva el campo por compatibilidad, sin volver a afectar los totales.
        descuento_valor = Decimal('0.00')

    total = total_detalles

    resultado = {
        'subtotal': q(subtotal),
        'iva': q(iva),
        'descuento_valor': q(descuento_valor),
        'total': q(total),
    }

    if efectivo_recibido is not None:
        cambio = to_decimal(efectivo_recibido) - resultado['total']
        resultado['cambio'] = q(cambio if cambio > 0 else Decimal('0'))

    return resultado
