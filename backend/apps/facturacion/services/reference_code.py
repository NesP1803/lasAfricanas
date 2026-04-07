from __future__ import annotations

import uuid

from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.ventas.models import Venta


def generate_unique_reference_code(venta_id: int, numero: str | None = None) -> str:
    ts = timezone.now().strftime('%Y%m%d%H%M%S')
    short = uuid.uuid4().hex[:8].upper()
    if numero:
        return f'{numero}-{ts}-{short}'
    return f'VENTA-{venta_id}-{ts}-{short}'


def resolve_reference_code(
    *,
    venta: Venta,
    factura_existente: FacturaElectronica | None,
    numero: str,
) -> str:
    if factura_existente and str(factura_existente.reference_code or '').strip():
        return str(factura_existente.reference_code).strip()
    return generate_unique_reference_code(venta.id, numero)
