"""Servicios administrativos para rangos de numeración Factus."""

from __future__ import annotations

from datetime import date
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.constants import FACTUS_CODE_TO_LOCAL, LOCAL_LABELS, normalize_local_document_code
from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_client import (
    FactusAPIError,
    FactusAuthError,
    FactusClient,
    FactusValidationError,
)
from apps.facturacion.services.factus_environment import resolve_factus_environment

logger = logging.getLogger(__name__)

DOCUMENT_CODE_MAP: dict[str, str] = dict(FACTUS_CODE_TO_LOCAL)

DOCUMENT_NAME_MAP: dict[str, str] = {
    code: LOCAL_LABELS.get(local_code, local_code)
    for code, local_code in DOCUMENT_CODE_MAP.items()
}


def _remote_document_value(raw: dict[str, Any]) -> str:
    return str(raw.get('document') or raw.get('document_code') or '').strip()


def map_remote_document_to_local(raw_document: str) -> str:
    return normalize_local_document_code(raw_document, default='')


def get_authorized_software_ranges(document_code: str) -> list[dict[str, Any]]:
    return [
        item
        for item in get_software_ranges()
        if map_remote_document_to_local(_remote_document_value(item)) == document_code
    ]


def get_authorized_software_range_ids(document_code: str) -> set[int]:
    return {
        int(item.get('id') or item.get('numbering_range_id') or 0)
        for item in get_authorized_software_ranges(document_code=document_code)
        if int(item.get('id') or item.get('numbering_range_id') or 0) > 0
    }


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    parsed = str(value).split('T')[0].strip()
    if not parsed:
        return None
    return date.fromisoformat(parsed)


def _normalize_payload(raw: dict[str, Any], *, software_ids: set[int] | None = None) -> dict[str, Any]:
    doc_code = _remote_document_value(raw)
    mapped_doc_code = map_remote_document_to_local(doc_code)
    factus_id = int(raw.get('id') or raw.get('numbering_range_id') or 0)
    is_expired = bool(raw.get('is_expired', False))
    is_active = bool(raw.get('is_active', True)) and not is_expired

    return {
        'factus_id': factus_id,
        'factus_range_id': factus_id,
        'document_code': mapped_doc_code,
        'document_name': DOCUMENT_NAME_MAP.get(doc_code, doc_code or mapped_doc_code),
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


def normalize_software_range(raw: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un rango remoto asociado al software para consumo de UI/validaciones."""
    factus_id = int(raw.get('id') or raw.get('numbering_range_id') or 0)
    doc_code = _remote_document_value(raw)
    mapped_document_code = map_remote_document_to_local(doc_code)
    is_expired = bool(raw.get('is_expired', False))
    is_active_remote = bool(raw.get('is_active', True)) and not is_expired
    is_associated = bool(raw.get('is_associated_to_software', True))
    normalized = {
        'factus_range_id': factus_id,
        'document_code': mapped_document_code,
        'document_name': DOCUMENT_NAME_MAP.get(doc_code, doc_code or mapped_document_code),
        'prefix': str(raw.get('prefix') or '').strip(),
        'from': int(raw.get('from') or 1),
        'to': int(raw.get('to') or 1),
        'current': int(raw.get('current') or raw.get('from') or 1),
        'resolution_number': str(raw.get('resolution_number') or '').strip(),
        'start_date': _as_date(raw.get('start_date') or raw.get('valid_from')),
        'end_date': _as_date(raw.get('end_date') or raw.get('valid_to')),
        'technical_key': str(raw.get('technical_key') or '').strip(),
        'is_active_remote': is_active_remote,
        'is_associated_to_software': is_associated,
    }
    # Compatibilidad con payloads frontend existentes.
    normalized['remote_id'] = factus_id
    normalized['document'] = doc_code
    normalized['is_active'] = is_active_remote
    return normalized


def list_available_authorized_ranges(document_code: str) -> list[dict[str, Any]]:
    """Lista rangos autorizados asociados al software con un payload normalizado estable."""
    software_ranges = get_software_ranges()
    normalized = [
        normalize_software_range(item)
        for item in software_ranges
        if map_remote_document_to_local(_remote_document_value(item)) == document_code
    ]
    logger.info(
        'facturacion.rangos.autorizados document_code=%s software_ranges=%s matched=%s',
        document_code,
        len(software_ranges),
        len(normalized),
    )
    return normalized



def list_ranges() -> list[dict[str, Any]]:
    payload = FactusClient().get_numbering_ranges()
    if isinstance(payload, list):
        return payload
    data = payload.get('data', payload) if isinstance(payload, dict) else []
    if isinstance(data, list):
        logger.info('facturacion.rangos.factus.response parsed=list count=%s', len(data))
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


def get_range_resilient(factus_id: int) -> dict[str, Any]:
    try:
        payload = get_range(factus_id)
        return {'payload': payload, 'unavailable': False, 'error': ''}
    except (FactusAPIError, FactusAuthError, FactusValidationError) as exc:
        status_code = int(getattr(exc, 'status_code', 0) or 0)
        if status_code in {403, 404}:
            return {'payload': None, 'unavailable': True, 'error': str(exc)}
        raise


def create_range(payload: dict[str, Any]) -> dict[str, Any]:
    return FactusClient().create_numbering_range(payload)


def delete_range(factus_id: int) -> dict[str, Any]:
    return FactusClient().delete_numbering_range(factus_id)


def update_range_current(factus_id: int, current: int) -> dict[str, Any]:
    return FactusClient().update_numbering_range_current(factus_id=factus_id, current=current)


def get_software_ranges() -> list[dict[str, Any]]:
    client = FactusClient()
    logger.info(
        'facturacion.rangos.factus.request endpoint=%s',
        client.numbering_ranges_dian_path,
    )
    payload = client.get_software_numbering_ranges()
    data = payload.get('data', payload) if isinstance(payload, dict) else payload
    if isinstance(data, list):
        logger.info('facturacion.rangos.factus.response parsed=list count=%s', len(data))
        return data
    if isinstance(data, dict):
        nested = data.get('data', data.get('numbering_ranges', []))
        if isinstance(nested, list):
            logger.info('facturacion.rangos.factus.response parsed=nested_list count=%s', len(nested))
            return nested
    logger.warning('facturacion.rangos.factus.response parsed=empty payload_type=%s', type(payload).__name__)
    return []



def get_software_ranges_resilient() -> dict[str, Any]:
    try:
        ranges = get_software_ranges()
        return {'ranges': ranges, 'degraded': False, 'error': ''}
    except (FactusAPIError, FactusAuthError, FactusValidationError) as exc:
        return {
            'ranges': [],
            'degraded': True,
            'error': str(exc),
        }

def sync_ranges_to_db() -> list[RangoNumeracionDIAN]:
    environment = resolve_factus_environment()
    ranges = list_ranges()
    software_status = get_software_ranges_resilient()
    software_ranges = software_status['ranges']
    software_keys = {
        (
            int(item.get('id') or item.get('numbering_range_id') or 0),
            map_remote_document_to_local(_remote_document_value(item)),
        )
        for item in software_ranges
        if item.get('id') or item.get('numbering_range_id')
    }

    synced: list[RangoNumeracionDIAN] = []
    synced_ids: list[int] = []
    with transaction.atomic():
        for raw in ranges:
            normalized = _normalize_payload(raw, software_ids=None)
            if not normalized['factus_id'] or not normalized['prefijo']:
                continue
            normalized['is_associated_to_software'] = (
                normalized['factus_id'],
                normalized['document_code'],
            ) in software_keys
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
        authorized_factura_ids = get_authorized_software_range_ids(document_code='FACTURA_VENTA')
        if authorized_factura_ids:
            RangoNumeracionDIAN.objects.filter(
                environment=environment,
                document_code='FACTURA_VENTA',
                is_selected_local=True,
            ).exclude(
                factus_id__in=authorized_factura_ids,
            ).update(is_selected_local=False)
        else:
            RangoNumeracionDIAN.objects.filter(
                environment=environment,
                document_code='FACTURA_VENTA',
                is_selected_local=True,
            ).update(is_selected_local=False)

    return synced
