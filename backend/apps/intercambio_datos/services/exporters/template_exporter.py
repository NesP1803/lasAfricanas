from io import BytesIO
from openpyxl import Workbook

TEMPLATE_FIELDS = {
    'clientes': ['numero_documento', 'nombre', 'telefono', 'email', 'direccion', 'ciudad'],
    'productos': ['codigo', 'nombre', 'categoria', 'proveedor', 'precio_costo', 'precio_venta', 'impuesto'],
    'proveedores': ['nit', 'nombre', 'telefono', 'email', 'direccion'],
    'categorias': ['nombre', 'descripcion'],
    'impuestos': ['nombre', 'porcentaje'],
    'motos': ['placa', 'marca', 'modelo', 'color', 'cliente_documento'],
    'mecanicos': ['nombre', 'telefono', 'email', 'direccion', 'ciudad'],
    'ventas': ['numero_comprobante', 'cliente_documento', 'subtotal', 'iva', 'total', 'medio_pago'],
    'detalles_venta': ['venta_numero', 'producto_codigo', 'cantidad', 'precio_unitario', 'iva_porcentaje'],
}


def build_template(codigo):
    wb = Workbook()
    ws = wb.active
    ws.title = codigo
    ws.append(TEMPLATE_FIELDS[codigo])
    output = BytesIO()
    wb.save(output)
    return output.getvalue()
