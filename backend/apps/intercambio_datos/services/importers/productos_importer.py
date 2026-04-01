from decimal import Decimal
from apps.inventario.models import Producto, Categoria, Proveedor
from apps.core.models import Impuesto
from apps.intercambio_datos.services.rules.tax_rules import parse_tax_value


def import_row(data, precio_fuente='FINAL'):
    codigo = str(data.get('codigo', '')).strip()
    if not codigo:
        return 'ERROR', None, 'codigo requerido'
    categoria_nombre = str(data.get('categoria', '')).strip() or 'SIN CATEGORIA'
    categoria, _ = Categoria.objects.get_or_create(nombre=categoria_nombre, defaults={'descripcion': ''})

    proveedor = None
    proveedor_nombre = str(data.get('proveedor', '')).strip()
    if proveedor_nombre:
        proveedor, _ = Proveedor.objects.get_or_create(nombre=proveedor_nombre)

    price = Decimal(str(data.get('precio_venta') or '0') or '0')
    costo = Decimal(str(data.get('precio_costo') or price) or '0')
    tax_payload, warnings = parse_tax_value(data.get('impuesto', data.get('iva_porcentaje', '19')))
    if tax_payload is None:
        return 'ERROR', None, ';'.join(warnings)

    Impuesto.objects.get_or_create(nombre='IVA', porcentaje=tax_payload['iva_porcentaje'])

    defaults = {
        'nombre': str(data.get('nombre', '')).strip() or codigo,
        'descripcion': str(data.get('descripcion', '')).strip(),
        'categoria': categoria,
        'proveedor': proveedor,
        'precio_venta': price,
        'precio_costo': costo,
        'precio_venta_minimo': Decimal(str(data.get('precio_venta_minimo') or price) or '0'),
        'stock': Decimal(str(data.get('stock') or '0') or '0'),
        'stock_minimo': Decimal(str(data.get('stock_minimo') or '0') or '0'),
        'iva_porcentaje': tax_payload['iva_porcentaje'],
        'iva_exento': tax_payload['iva_exento'],
    }
    if precio_fuente not in {'FINAL', 'BASE_SIN_IVA'}:
        warnings.append('precio_fuente inválido, revisión manual')
    instance, created = Producto.objects.update_or_create(codigo=codigo, defaults=defaults)
    return ('INSERTADA' if created else 'ACTUALIZADA'), instance, ';'.join(warnings)
