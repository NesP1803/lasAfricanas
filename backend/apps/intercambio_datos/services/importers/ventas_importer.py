from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.ventas.models import Venta
from apps.intercambio_datos.services.mappers.relation_resolver import resolve_cliente_by_documento


def import_row(data, fallback_user):
    numero = str(data.get('numero_comprobante', '')).strip()
    if not numero:
        return 'ERROR', None, 'numero_comprobante requerido'
    cliente = resolve_cliente_by_documento(data.get('cliente_documento'))
    if not cliente:
        return 'ERROR', None, 'cliente no encontrado'
    User = get_user_model()
    vendedor = User.objects.filter(username=str(data.get('vendedor', '')).strip()).first() or fallback_user
    defaults = {
        'cliente': cliente,
        'vendedor': vendedor,
        'subtotal': Decimal(str(data.get('subtotal') or '0')),
        'descuento_porcentaje': Decimal(str(data.get('descuento_porcentaje') or '0')),
        'descuento_valor': Decimal(str(data.get('descuento_valor') or '0')),
        'iva': Decimal(str(data.get('iva') or '0')),
        'total': Decimal(str(data.get('total') or '0')),
        'medio_pago': str(data.get('medio_pago') or 'EFECTIVO').upper(),
        'estado': 'COBRADA',
    }
    obj, created = Venta.objects.update_or_create(numero_comprobante=numero, defaults=defaults)
    return ('INSERTADA' if created else 'ACTUALIZADA'), obj, ''
