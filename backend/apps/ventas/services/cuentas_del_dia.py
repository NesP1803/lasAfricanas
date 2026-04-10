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

    return {
        'ventas_queryset': ventas,
        'total_ventas': total_facturas + total_remisiones,
        'total_facturado': totales.get('total_facturado') or Decimal('0'),
        'total_cotizaciones': 0,
        'total_remisiones': total_remisiones,
        'total_facturas': total_facturas,
        'total_facturas_valor': totales.get('total_facturas_valor') or Decimal('0'),
        'total_remisiones_valor': totales.get('total_remisiones_valor') or Decimal('0'),
    }
