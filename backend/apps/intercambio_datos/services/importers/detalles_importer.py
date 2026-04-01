from decimal import Decimal
from apps.ventas.models import DetalleVenta
from apps.intercambio_datos.services.mappers.relation_resolver import resolve_producto_by_codigo, resolve_venta_by_numero


def import_row(data):
    venta = resolve_venta_by_numero(data.get('venta_numero'))
    producto = resolve_producto_by_codigo(data.get('producto_codigo'))
    if not venta or not producto:
        return 'ERROR', None, 'detalle huérfano: venta/producto inexistente'
    qty = Decimal(str(data.get('cantidad') or '0'))
    pu = Decimal(str(data.get('precio_unitario') or '0'))
    iva = Decimal(str(data.get('iva_porcentaje') or '0'))
    subtotal = Decimal(str(data.get('subtotal') or (qty * pu)))
    total = Decimal(str(data.get('total') or subtotal))
    obj, created = DetalleVenta.objects.update_or_create(
        venta=venta,
        producto=producto,
        defaults={
            'cantidad': qty,
            'precio_unitario': pu,
            'descuento_unitario': Decimal(str(data.get('descuento_unitario') or '0')),
            'iva_porcentaje': iva,
            'subtotal': subtotal,
            'total': total,
        }
    )
    return ('INSERTADA' if created else 'ACTUALIZADA'), obj, ''
