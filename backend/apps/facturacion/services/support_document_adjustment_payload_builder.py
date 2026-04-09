"""Builder de payload para notas de ajuste de documento soporte en Factus."""

from __future__ import annotations

from typing import Any

from apps.facturacion.models import DocumentoSoporteElectronico
from apps.facturacion.services.consecutivo_service import resolve_electronic_numbering_range_id


def build_adjustment_payload(
    documento_soporte: DocumentoSoporteElectronico,
    motivo: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construye el payload de nota de ajuste con referencia explícita al documento soporte original."""
    numbering_range_id = int(resolve_electronic_numbering_range_id('NOTA_AJUSTE_DOCUMENTO_SOPORTE') or 0)
    return {
        'reference_support_document_number': documento_soporte.number,
        'reference_support_document_cufe': documento_soporte.cufe,
        'adjustment_reason': motivo,
        'numbering_range_id': numbering_range_id,
        'items': items,
    }
