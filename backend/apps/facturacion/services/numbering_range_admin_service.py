"""Servicios administrativos para rangos de numeración Factus."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.factus_environment import resolve_factus_environment

DOCUMENT_CODE_MAP: dict[str, str] = {
    '21': 'FACTURA_VENTA',
    '22': 'NOTA_CREDITO',
    '23': 'NOTA_DEBITO',
    '24': 'DOCUMENTO_SOPORTE',
    '25': 'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
    '26': 'NOMINA',
    '27': 'NOTA_AJUSTE_NOMINA',
    '28': 'NOTA_ELIMINACION_NOMINA',
    '30': 'FACTURA_TALONARIO_PAPEL',
}

DOCUMENT_NAME_MAP: dict[str, str] = {
    '21': 'Factura de Venta',
    '22': 'Nota Crédito',
    '23': 'Nota Débito',
    '24': 'Documento Soporte',
    '25': 'Nota de Ajuste Documento Soporte',
    '26': 'Nómina',
    '27': 'Nota de Ajuste Nómina',
    '28': 'Nota de eliminación de nómina',
    '30': 'Factura de talonario y de papel',
}


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    parsed = str(value).split('T')[0].strip()
    if not parsed:
        return None
    return date.fromisoformat(parsed)


def _normalize_payload(raw: dict[str, Any], *, software_ids: set[int] | None = None) -> dict[str, Any]:
    doc_code = str(raw.get('document') or raw.get('document_code') or '').strip()
    mapped_doc_code = DOCUMENT_CODE_MAP.get(doc_code, 'FACTURA_VENTA')
    factus_id = int(raw.get('id') or raw.get('numbering_range_id') or 0)
    is_expired = bool(raw.get('is_expired', False))
    is_active = bool(raw.get('is_active', True)) and not is_expired

    return {
        'factus_id': factus_id,
        'factus_range_id': factus_id,
        'document_code': mapped_doc_code,
        'document_name': DOCUMENT_NAME_MAP.get(doc_code, mapped_doc_code),
        'prefijo': str(raw.get('prefix') or '').strip(),
        'desde': int(raw.get('from') or 1),
        'hasta': int(raw.get('to') or 1),
        'consecutivo_actual': int(raw.get('current') or raw.get('from') or 1),
        'resolucion': str(raw.get('resolution_number') or '').strip(),
        'fecha_autorizacion': _as_date(raw.get('start_date') or raw.get('valid_from')),
        'fecha_expiracion': _as_date(raw.get('end_date') or raw.get('valid_to')),
        'technical_key': str(raw.get('technical_key') or '').strip(),
        'is_active_remote': is_active,
        'is_expired_remote': is_expired,
        'is_associated_to_software': factus_id in (software_ids or set()),
        'activo': is_active,
        'last_synced_at': timezone.now(),
        'metadata_json': raw,
    }


def list_ranges() -> list[dict[str, Any]]:
    payload = FactusClient().get_numbering_ranges()
    if isinstance(payload, list):
        return payload
    data = payload.get('data', payload) if isinstance(payload, dict) else []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        nested = data.get('data', data.get('numbering_ranges', []))
        if isinstance(nested, list):
            return nested
        if isinstance(nested, dict):
            return nested.get('numbering_ranges', [])
    return []


def get_range(factus_id: int) -> dict[str, Any]:
    return FactusClient().get_numbering_range(factus_id)


def create_range(payload: dict[str, Any]) -> dict[str, Any]:
    return FactusClient().create_numbering_range(payload)


def delete_range(factus_id: int) -> dict[str, Any]:
    return FactusClient().delete_numbering_range(factus_id)


def update_range_current(factus_id: int, current: int) -> dict[str, Any]:
    return FactusClient().update_numbering_range_current(factus_id=factus_id, current=current)


def get_software_ranges() -> list[dict[str, Any]]:
    payload = FactusClient().get_software_numbering_ranges()
    data = payload.get('data', payload) if isinstance(payload, dict) else payload
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        nested = data.get('data', data.get('numbering_ranges', []))
        if isinstance(nested, list):
            return nested
    return []


def sync_ranges_to_db() -> list[RangoNumeracionDIAN]:
    environment = resolve_factus_environment()
    ranges = list_ranges()
    software_ranges = get_software_ranges()
    software_ids = {
        int(item.get('id') or item.get('numbering_range_id') or 0)
        for item in software_ranges
        if item.get('id') or item.get('numbering_range_id')
    }

    synced: list[RangoNumeracionDIAN] = []
    synced_ids: list[int] = []
    with transaction.atomic():
        for raw in ranges:
            normalized = _normalize_payload(raw, software_ids=software_ids)
            if not normalized['factus_id'] or not normalized['prefijo']:
                continue
            synced_ids.append(normalized['factus_id'])
            rango, _ = RangoNumeracionDIAN.objects.update_or_create(
                factus_id=normalized['factus_id'],
                environment=environment,
                document_code=normalized['document_code'],
                defaults=normalized,
            )
            synced.append(rango)

        if synced_ids:
            RangoNumeracionDIAN.objects.filter(environment=environment).exclude(
                factus_id__in=synced_ids
            ).update(is_active_remote=False)

    return synced
