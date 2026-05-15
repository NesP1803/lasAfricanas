from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.db.models import Count, Prefetch, Q, QuerySet, Sum
from django.utils import timezone

from apps.ventas.models import DetalleVenta, Venta


TIPOS_COMPROBANTE_CUENTAS_DIA = ('FACTURA', 'REMISION')


def _parse_local_date_range(fecha_inicio: str | None, fecha_fin: str | None) -> tuple[datetime | None, datetime | None]:
    tz = timezone.get_current_timezone()
    inicio_dt = fin_dt = None

    if fecha_inicio:
        inicio_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        inicio_dt = timezone.make_aware(datetime.combine(inicio_date, time.min), tz)

    if fecha_fin:
        fin_date = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        fin_dt = timezone.make_aware(datetime.combine(fin_date, time.max), tz)

    return inicio_dt, fin_dt


def get_cuentas_del_dia_queryset(
    fecha_inicio: str | None,
    fecha_fin: str | None,
    *,
    sucursal: int | None = None,
    caja: int | None = None,
    base_queryset: QuerySet[Venta] | None = None,
) -> QuerySet[Venta]:
    """Retorna el queryset base para cuentas del día (tirilla/dashboard)."""
    if base_queryset is not None:
        # Reutiliza prefetch/select_related ya aplicados por el caller.
        # Evita colisionar con otro Prefetch('detalles', queryset=...) distinto.
        ventas = base_queryset
    else:
        detalles_queryset = DetalleVenta.objects.select_related(
            'producto',
            'producto__categoria',
            'producto__proveedor',
        )
        ventas = Venta.objects.select_related(
            'cliente', 'vendedor', 'factura_electronica_factus'
        ).prefetch_related(Prefetch('detalles', queryset=detalles_queryset))

    ventas = ventas.filter(
        estado='COBRADA',
        tipo_comprobante__in=TIPOS_COMPROBANTE_CUENTAS_DIA,
    )

    inicio_dt, fin_dt = _parse_local_date_range(fecha_inicio, fecha_fin)
    if inicio_dt:
        ventas = ventas.filter(fecha__gte=inicio_dt)
    if fin_dt:
        ventas = ventas.filter(fecha__lte=fin_dt)

    return ventas


def build_cuentas_del_dia_summary(
    fecha_inicio: str | None,
    fecha_fin: str | None,
    *,
    sucursal: int | None = None,
    caja: int | None = None,
    base_queryset: QuerySet[Venta] | None = None,
) -> dict:
    ventas = get_cuentas_del_dia_queryset(
        fecha_inicio,
        fecha_fin,
        sucursal=sucursal,
        caja=caja,
        base_queryset=base_queryset,
    )

    totales = ventas.aggregate(
        total_facturado=Sum('total'),
        total_remisiones=Count('id', filter=Q(tipo_comprobante='REMISION')),
        total_facturas=Count('id', filter=Q(tipo_comprobante='FACTURA')),
        total_facturas_valor=Sum('total', filter=Q(tipo_comprobante='FACTURA')),
        total_remisiones_valor=Sum('total', filter=Q(tipo_comprobante='REMISION')),
    )

    total_facturas = totales.get('total_facturas') or 0
    total_remisiones = totales.get('total_remisiones') or 0

    resumen_tirilla = {
        'FACTURA': build_cuentas_del_dia_ticket_summary(fecha_inicio, fecha_fin, 'FACTURA', base_queryset=base_queryset),
        'REMISION': build_cuentas_del_dia_ticket_summary(fecha_inicio, fecha_fin, 'REMISION', base_queryset=base_queryset),
    }

    return {
        'ventas_queryset': ventas,
        'total_ventas': total_facturas + total_remisiones,
        'total_facturado': totales.get('total_facturado') or Decimal('0'),
        'total_cotizaciones': 0,
        'total_remisiones': total_remisiones,
        'total_facturas': total_facturas,
        'total_facturas_valor': totales.get('total_facturas_valor') or Decimal('0'),
        'total_remisiones_valor': totales.get('total_remisiones_valor') or Decimal('0'),
        'resumen_tirilla': resumen_tirilla,
    }


VALID_STATES_MONEY = ('COBRADA', 'FACTURADA')


def _decimal_to_str(value: Decimal) -> str:
    return f"{(value or Decimal('0')).quantize(Decimal('0.01'))}"


def _normalize_iva_label(detalle: DetalleVenta) -> str:
    producto = getattr(detalle, 'producto', None)
    if detalle.iva_porcentaje == 0 or (producto and getattr(producto, 'iva_exento', False)):
        return 'E'
    iva = detalle.iva_porcentaje.quantize(Decimal('0.01'))
    if iva == iva.to_integral_value():
        return str(int(iva))
    return format(iva.normalize(), 'f').rstrip('0').rstrip('.')


def build_cuentas_del_dia_ticket_summary(fecha_inicio: str | None, fecha_fin: str | None, tipo_comprobante: str, *, base_queryset: QuerySet[Venta] | None = None) -> dict:
    ventas_base = base_queryset or Venta.objects.all()
    inicio_dt, fin_dt = _parse_local_date_range(fecha_inicio, fecha_fin)

    ventas_tipo = ventas_base.filter(tipo_comprobante=tipo_comprobante)
    if inicio_dt:
        ventas_tipo = ventas_tipo.filter(fecha__gte=inicio_dt)
    if fin_dt:
        ventas_tipo = ventas_tipo.filter(fecha__lte=fin_dt)

    ventas_validas = ventas_tipo.filter(estado__in=VALID_STATES_MONEY)

    resumen_iva = {}
    resumen_categorias = {}
    total_desc = Decimal('0')
    for venta in ventas_validas:
        for detalle in venta.detalles.all():
            label = _normalize_iva_label(detalle)
            bucket = resumen_iva.setdefault(label, {
                'tipo': label, 'compra': Decimal('0'), 'base': Decimal('0'), 'iva': Decimal('0'), 'descuento': Decimal('0')
            })
            bucket['compra'] += detalle.total
            bucket['base'] += detalle.subtotal
            bucket['iva'] += (detalle.total - detalle.subtotal)
            descuento = (detalle.cantidad or Decimal('0')) * (detalle.descuento_unitario or Decimal('0'))
            if descuento:
                bucket['descuento'] -= descuento
                total_desc -= descuento

            categoria = ((getattr(detalle.producto, 'categoria', None) and detalle.producto.categoria.nombre) or 'SIN CATEGORÍA').upper()
            resumen_categorias[categoria] = resumen_categorias.get(categoria, Decimal('0')) + detalle.total

    total_facturado = ventas_validas.aggregate(total=Sum('total')).get('total') or Decimal('0')
    total_documentos = ventas_validas.count()

    totales_iva = {
        'compra': sum((v['compra'] for v in resumen_iva.values()), Decimal('0')),
        'base': sum((v['base'] for v in resumen_iva.values()), Decimal('0')),
        'iva': sum((v['iva'] for v in resumen_iva.values()), Decimal('0')),
        'descuento': total_desc,
    }

    estados = [
        {'estado': 'ANULADAS', 'cantidad': ventas_tipo.filter(estado='ANULADA').count()},
        {'estado': 'FACTURADAS', 'cantidad': total_documentos},
    ]

    medios = {}
    for venta in ventas_validas:
        medio = (venta.get_medio_pago_display() or venta.medio_pago or '').upper()
        item = medios.setdefault(medio, {'cantidad': 0, 'medio_pago': medio, 'facturado': Decimal('0')})
        item['cantidad'] += 1
        item['facturado'] += venta.total

    return {
        'tipo_comprobante': tipo_comprobante,
        'documento_label': 'Facturas' if tipo_comprobante == 'FACTURA' else 'Remisiones',
        'titulo': 'COMPROBANTE DE FACTURACIÓN' if tipo_comprobante == 'FACTURA' else 'COMPROBANTE DE REMISIONES',
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'total_documentos': total_documentos,
        'total_facturado': _decimal_to_str(total_facturado),
        'resumen_iva': [
            {k: (_decimal_to_str(vv) if isinstance(vv, Decimal) else vv) for k, vv in row.items()}
            for row in sorted(resumen_iva.values(), key=lambda x: (x['tipo'] == 'E', x['tipo']))
        ],
        'totales_iva': {k: _decimal_to_str(v) for k, v in totales_iva.items()},
        'resumen_categorias': [
            {'categoria': cat, 'facturado': _decimal_to_str(total)}
            for cat, total in sorted(resumen_categorias.items(), key=lambda x: x[0])
        ],
        'resumen_estados': estados,
        'resumen_medios_pago': [
            {'cantidad': row['cantidad'], 'medio_pago': row['medio_pago'], 'facturado': _decimal_to_str(row['facturado'])}
            for row in sorted(medios.values(), key=lambda x: x['medio_pago'])
        ],
    }
