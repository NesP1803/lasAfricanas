"""Sincronización de rangos de numeración DIAN desde Factus."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_client import FactusClient


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    parsed = str(value).split('T')[0].strip()
    if not parsed:
        return None
    return date.fromisoformat(parsed)


def sync_numbering_ranges() -> list[RangoNumeracionDIAN]:
    """Sincroniza rangos de numeración desde Factus y retorna los rangos procesados."""
    payload = FactusClient().get_numbering_ranges()
    ranges = payload.get('data', payload)
    if isinstance(ranges, dict):
        ranges = ranges.get('numbering_ranges', [])

    synced: list[RangoNumeracionDIAN] = []
    for raw_range in ranges:
        prefijo = str(raw_range.get('prefix', raw_range.get('prefijo', ''))).strip()
        if not prefijo:
            continue

        desde = int(raw_range.get('from', raw_range.get('desde', 1)) or 1)
        hasta = int(raw_range.get('to', raw_range.get('hasta', desde)) or desde)
        resolucion = str(raw_range.get('resolution_number', raw_range.get('resolution', raw_range.get('resolucion', '')))).strip()
        consecutivo_actual = int(raw_range.get('current', raw_range.get('consecutivo_actual', desde)) or desde)

        rango, _ = RangoNumeracionDIAN.objects.update_or_create(
            prefijo=prefijo,
            defaults={
                'desde': desde,
                'hasta': hasta,
                'resolucion': resolucion,
                'consecutivo_actual': consecutivo_actual,
                'fecha_autorizacion': _as_date(raw_range.get('valid_from', raw_range.get('fecha_autorizacion'))),
                'fecha_expiracion': _as_date(raw_range.get('valid_to', raw_range.get('fecha_expiracion'))),
                'activo': bool(raw_range.get('is_active', raw_range.get('activo', True))),
            },
        )
        synced.append(rango)

    return synced
