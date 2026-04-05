"""Sincronización de rangos de numeración DIAN desde Factus."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.factus_environment import resolve_factus_environment

logger = logging.getLogger(__name__)


def _resolve_document_code(raw_range: dict[str, Any]) -> str:
    raw_value = str(
        raw_range.get('document')
        or raw_range.get('document_code')
        or raw_range.get('voucher_type')
        or ''
    ).strip()
    raw = raw_value.upper()
    compact = (
        raw.replace('Á', 'A')
        .replace('É', 'E')
        .replace('Í', 'I')
        .replace('Ó', 'O')
        .replace('Ú', 'U')
        .replace(' ', '_')
        .replace('-', '_')
    )
    if raw in {'NOTA_CREDITO', 'CREDIT_NOTE', 'NC'} or compact in {'NOTA_CREDITO', 'CREDIT_NOTE', 'NC'}:
        return 'NOTA_CREDITO'
    if raw in {'DOCUMENTO_SOPORTE', 'SUPPORT_DOCUMENT', 'DS'} or compact in {
        'DOCUMENTO_SOPORTE',
        'SUPPORT_DOCUMENT',
        'DS',
    }:
        return 'DOCUMENTO_SOPORTE'
    if raw in {'NOTA_AJUSTE_DOCUMENTO_SOPORTE', 'SUPPORT_DOCUMENT_ADJUSTMENT_NOTE', 'NDA', 'NADS'} or compact in {
        'NOTA_DE_AJUSTE_DOCUMENTO_SOPORTE',
        'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        'SUPPORT_DOCUMENT_ADJUSTMENT_NOTE',
        'NDA',
        'NADS',
    }:
        return 'NOTA_AJUSTE_DOCUMENTO_SOPORTE'
    if raw in {'NOTA_DEBITO', 'DEBIT_NOTE'} or compact in {'NOTA_DEBITO', 'DEBIT_NOTE'}:
        return 'NOTA_DEBITO'
    return 'FACTURA_VENTA'


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    parsed = str(value).split('T')[0].strip()
    if not parsed:
        return None
    return date.fromisoformat(parsed)


def sync_numbering_ranges() -> list[RangoNumeracionDIAN]:
    """Sincroniza rangos de numeración desde Factus y retorna los rangos procesados."""
    environment = resolve_factus_environment()
    payload = FactusClient().get_numbering_ranges()
    ranges: list[dict[str, Any]] = []
    if isinstance(payload, list):
        ranges = payload
    elif isinstance(payload, dict):
        data = payload.get('data', payload)
        if isinstance(data, list):
            ranges = data
        elif isinstance(data, dict):
            nested = data.get('data')
            if isinstance(nested, list):
                ranges = nested
            elif isinstance(nested, dict):
                ranges = nested.get('numbering_ranges', [])
            else:
                ranges = data.get('numbering_ranges', [])
        else:
            ranges = []

    synced: list[RangoNumeracionDIAN] = []
    synced_ids: list[int] = []
    for raw_range in ranges:
        factus_range_id = raw_range.get('id') or raw_range.get('numbering_range_id')
        if factus_range_id is None:
            continue
        prefijo = str(raw_range.get('prefix', raw_range.get('prefijo', ''))).strip()
        if not prefijo:
            continue

        desde = int(raw_range.get('from', raw_range.get('desde', 1)) or 1)
        hasta = int(raw_range.get('to', raw_range.get('hasta', desde)) or desde)
        resolucion = str(raw_range.get('resolution_number', raw_range.get('resolution', raw_range.get('resolucion', '')))).strip()
        consecutivo_actual = int(raw_range.get('current', raw_range.get('consecutivo_actual', desde)) or desde)

        document_code = _resolve_document_code(raw_range)
        rango, _ = RangoNumeracionDIAN.objects.update_or_create(
            factus_range_id=factus_range_id,
            environment=environment,
            document_code=document_code,
            defaults={
                'desde': desde,
                'hasta': hasta,
                'resolucion': resolucion,
                'consecutivo_actual': consecutivo_actual,
                'fecha_autorizacion': _as_date(raw_range.get('valid_from', raw_range.get('fecha_autorizacion'))),
                'fecha_expiracion': _as_date(raw_range.get('valid_to', raw_range.get('fecha_expiracion'))),
                'prefijo': prefijo,
                'activo': bool(raw_range.get('is_active', raw_range.get('activo', True)))
                and not bool(raw_range.get('is_expired', False)),
                'is_active_remote': bool(raw_range.get('is_active', raw_range.get('activo', True)))
                and not bool(raw_range.get('is_expired', False)),
            },
        )
        synced.append(rango)
        if rango.factus_range_id is not None:
            synced_ids.append(int(rango.factus_range_id))

    RangoNumeracionDIAN.objects.filter(
        environment=environment,
    ).exclude(factus_range_id__in=synced_ids).update(is_active_remote=False)

    logger.info(
        'Sincronización Factus rangos: recibidos=%s persistidos=%s entorno=%s',
        len(ranges),
        len(synced),
        environment,
    )

    return synced
