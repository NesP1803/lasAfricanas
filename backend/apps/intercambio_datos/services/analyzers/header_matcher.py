import re


ENTITY_HEADERS = {
    'clientes': {'numero_documento', 'nombre', 'telefono', 'email', 'direccion', 'ciudad'},
    'productos': {'codigo', 'nombre', 'categoria', 'proveedor', 'precio_venta', 'precio_costo', 'impuesto'},
    'proveedores': {'nit', 'nombre', 'telefono', 'email', 'direccion'},
    'categorias': {'nombre', 'descripcion'},
    'impuestos': {'nombre', 'porcentaje'},
    'motos': {'placa', 'marca', 'modelo', 'cliente_documento'},
    'mecanicos': {'nombre', 'telefono', 'email'},
    'ventas': {'numero_comprobante', 'cliente_documento', 'total', 'medio_pago'},
    'detalles_venta': {'venta_numero', 'producto_codigo', 'cantidad', 'precio_unitario', 'iva_porcentaje'},
}


def normalize_header(value):
    value = str(value or '').strip().lower()
    value = re.sub(r'[%\s]+', '_', value)
    value = re.sub(r'[^a-z0-9_]', '', value)
    return value


def score_entity(headers):
    norm = {normalize_header(h) for h in headers if h}
    scores = {}
    for entity, expected in ENTITY_HEADERS.items():
        inter = len(norm.intersection(expected))
        score = inter / max(len(expected), 1)
        scores[entity] = round(score * 100, 2)
    return scores
