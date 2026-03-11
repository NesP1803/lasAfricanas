"""Builder de payload para notas crédito electrónicas Factus."""

from __future__ import annotations

from typing import Any

from apps.facturacion.models import FacturaElectronica


def build_credit_note_payload(factura: FacturaElectronica, motivo: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Construye el payload de nota crédito con referencia explícita a la factura original."""
    return {
        'reference_invoice_number': factura.number,
        'reference_invoice_cufe': factura.cufe,
        'credit_note_reason': motivo,
        'items': items,
    }
