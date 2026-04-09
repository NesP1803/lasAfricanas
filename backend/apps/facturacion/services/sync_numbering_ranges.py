"""Sincronización oficial de rangos DIAN asociados al software en Factus."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from apps.facturacion.constants import normalize_local_document_code
from apps.facturacion.models import FactusNumberingRange
from apps.facturacion.services.factus_client import FactusClient


FACTURA_VENTA = 'FACTURA_VENTA'


def _resolve_document_code(raw_range: dict[str, object]) -> str:
    return normalize_local_document_code(
        str(raw_range.get('document') or raw_range.get('document_code') or ''),
        default=FACTURA_VENTA,
    )


def _as_date(value: str | None) -> date:
    parsed = str(value or '').split('T')[0].strip()
    if not parsed:
        raise ValueError('Factus devolvió una fecha vacía en numbering-ranges/dian.')
    return date.fromisoformat(parsed)


def sync_factus_dian_ranges() -> list[FactusNumberingRange]:
    """Sincroniza rangos desde GET /v1/numbering-ranges/dian y reemplaza snapshot local."""
    payload = FactusClient().get_software_numbering_ranges()

    data = payload.get('data', payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        data = data.get('data', data.get('numbering_ranges', []))
    ranges = data if isinstance(data, list) else []

    today = timezone.now().date()
    FactusNumberingRange.objects.all().delete()

    created: list[FactusNumberingRange] = []
    for raw in ranges:
        end_date = _as_date(raw.get('end_date'))
        created.append(
            FactusNumberingRange.objects.create(
                document=_resolve_document_code(raw),
                prefix=str(raw.get('prefix') or '').strip(),
                resolution_number=str(raw.get('resolution_number') or '').strip(),
                from_number=int(raw.get('from') or 0),
                to_number=int(raw.get('to') or 0),
                start_date=_as_date(raw.get('start_date')),
                end_date=end_date,
                technical_key=str(raw.get('technical_key') or '').strip() or None,
                is_active=end_date >= today,
            )
        )

    return created


def sync_numbering_ranges() -> list[FactusNumberingRange]:
    """Compat wrapper para llamadas legadas."""
    return sync_factus_dian_ranges()
