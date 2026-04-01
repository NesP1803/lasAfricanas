from io import BytesIO
from openpyxl import Workbook
from apps.ventas.models import Cliente, Venta, DetalleVenta
from apps.inventario.models import Producto, Proveedor, Categoria, MovimientoInventario
from apps.core.models import Impuesto
from apps.taller.models import Moto, Mecanico


def _append_sheet(wb, name, headers, rows):
    ws = wb.create_sheet(title=name)
    ws.append(headers)
    for row in rows:
        ws.append(row)


def export_profile(codigo):
    wb = Workbook()
    wb.remove(wb.active)

    if codigo == 'ventas_detalles':
        _append_sheet(wb, 'ventas', ['numero_comprobante', 'cliente_documento', 'total'],
                      [[v.numero_comprobante, v.cliente.numero_documento, float(v.total)] for v in Venta.objects.all()[:500]])
        _append_sheet(wb, 'detalles_venta', ['venta_numero', 'producto_codigo', 'cantidad', 'total'],
                      [[d.venta.numero_comprobante, d.producto.codigo, float(d.cantidad), float(d.total)] for d in DetalleVenta.objects.select_related('venta', 'producto').all()[:2000]])
    elif codigo == 'productos_proveedores':
        _append_sheet(wb, 'productos', ['codigo', 'nombre', 'proveedor', 'precio_venta'],
                      [[p.codigo, p.nombre, p.proveedor.nombre if p.proveedor else '', float(p.precio_venta)] for p in Producto.objects.select_related('proveedor').all()[:2000]])
        _append_sheet(wb, 'proveedores', ['nit', 'nombre', 'telefono'],
                      [[p.nit, p.nombre, p.telefono] for p in Proveedor.objects.all()[:500]])
    elif codigo == 'clientes_motos':
        _append_sheet(wb, 'clientes', ['numero_documento', 'nombre', 'telefono'],
                      [[c.numero_documento, c.nombre, c.telefono] for c in Cliente.objects.all()[:2000]])
        _append_sheet(wb, 'motos', ['placa', 'marca', 'modelo', 'cliente_documento'],
                      [[m.placa, m.marca, m.modelo, m.cliente.numero_documento if m.cliente else ''] for m in Moto.objects.select_related('cliente').all()[:2000]])
    else:
        _append_sheet(wb, 'clientes', ['numero_documento', 'nombre'], [[c.numero_documento, c.nombre] for c in Cliente.objects.all()[:1000]])
        _append_sheet(wb, 'productos', ['codigo', 'nombre'], [[p.codigo, p.nombre] for p in Producto.objects.all()[:1000]])
        _append_sheet(wb, 'proveedores', ['nit', 'nombre'], [[p.nit, p.nombre] for p in Proveedor.objects.all()[:1000]])
        _append_sheet(wb, 'categorias', ['nombre'], [[c.nombre] for c in Categoria.objects.all()[:1000]])
        _append_sheet(wb, 'impuestos', ['nombre', 'porcentaje'], [[i.nombre, float(i.porcentaje)] for i in Impuesto.objects.all()[:1000]])
        _append_sheet(wb, 'mecanicos', ['nombre', 'telefono'], [[m.nombre, m.telefono] for m in Mecanico.objects.all()[:1000]])
        _append_sheet(wb, 'movimientos', ['producto', 'tipo', 'cantidad'], [[m.producto.codigo, m.tipo, float(m.cantidad)] for m in MovimientoInventario.objects.select_related('producto').all()[:1000]])

    out = BytesIO()
    wb.save(out)
    return out.getvalue()
