from __future__ import annotations

from decimal import Decimal


CENT = Decimal('0.01')


def to_decimal(value, default='0'):
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def q(value):
    return Decimal(value).quantize(CENT)


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

    total_bruto_linea = cantidad * precio_unitario
    descuento_linea = min(total_bruto_linea, cantidad * max(descuento_unitario, Decimal('0')))
    total_neto_linea_q = q(total_bruto_linea - descuento_linea)

    if detalle_es_exento(detalle, iva_porcentaje):
        base_linea_q = total_neto_linea_q
        iva_linea_q = Decimal('0.00')
    else:
        divisor_iva = Decimal('1') + (iva_porcentaje / Decimal('100'))
        base_linea_q = q(total_neto_linea_q / divisor_iva)
        iva_linea_q = q(total_neto_linea_q - base_linea_q)

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

    descuento_porcentaje = to_decimal(descuento_porcentaje)
    descuento_valor = to_decimal(descuento_valor)
    if descuento_porcentaje < 0 or descuento_valor < 0:
        raise ValueError('El descuento no puede ser negativo.')

    descuento_porcentaje_valor = (total_detalles * descuento_porcentaje) / Decimal('100')
    descuento_total = descuento_valor if descuento_valor > 0 else descuento_porcentaje_valor
    descuento_total = min(descuento_total, total_detalles)

    total = total_detalles - descuento_total

    resultado = {
        'subtotal': q(subtotal),
        'iva': q(iva),
        'descuento_valor': q(descuento_total),
        'total': q(total),
    }

    if efectivo_recibido is not None:
        cambio = to_decimal(efectivo_recibido) - resultado['total']
        resultado['cambio'] = q(cambio if cambio > 0 else Decimal('0'))

    return resultado
