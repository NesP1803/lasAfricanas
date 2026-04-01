from apps.ventas.models import Cliente, Venta
from apps.inventario.models import Producto


def resolve_cliente_by_documento(numero_documento):
    if not numero_documento:
        return None
    return Cliente.objects.filter(numero_documento=str(numero_documento).strip()).first()


def resolve_producto_by_codigo(codigo):
    if not codigo:
        return None
    return Producto.objects.filter(codigo=str(codigo).strip()).first()


def resolve_venta_by_numero(numero):
    if not numero:
        return None
    return Venta.objects.filter(numero_comprobante=str(numero).strip()).first()
