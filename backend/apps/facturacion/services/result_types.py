from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.facturacion.models import FacturaElectronica
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta


@dataclass
class FacturacionContext:
    """Contexto interno para orquestar facturación sin romper firma pública."""

    venta: Venta
    factura_existente: FacturaElectronica | None
    factura: FacturaElectronica | None
    triggered_by: Usuario | None
    payload: dict[str, Any]
    numero: str
    reference_code: str
    should_lock_expected_number: bool
