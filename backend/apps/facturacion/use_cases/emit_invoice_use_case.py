from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.facturacion.services import emitir_factura_completa
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta
from apps.ventas.services import cerrar_venta_local, validar_para_facturar_en_caja


@dataclass
class EmitInvoiceResult:
    venta: Venta
    factura: Any | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)



def emit_invoice_use_case(
    *,
    venta_id: int,
    triggered_by: Usuario | None,
    enforce_caja_rules: bool = False,
) -> EmitInvoiceResult:
    """
    Caso de uso único para emisión electrónica de una venta.

    Centraliza: precondiciones, cierre local, emisión electrónica y retorno
    estructurado para que las views solo compongan HTTP.
    """
    with transaction.atomic():
        venta = (
            Venta.objects.select_for_update()
            .select_related('cliente', 'vendedor')
            .prefetch_related('detalles', 'detalles__producto')
            .get(pk=venta_id)
        )
        if venta.tipo_comprobante != 'FACTURA':
            raise ValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
        if venta.estado == 'ANULADA':
            raise ValidationError('No se puede facturar una venta anulada.')

        if enforce_caja_rules:
            validar_para_facturar_en_caja(venta)

        if venta.estado not in {'COBRADA', 'FACTURADA'}:
            cerrar_venta_local(venta, triggered_by)

    flow_result = emitir_factura_completa(venta.id, triggered_by=triggered_by)
    venta.refresh_from_db()

    return EmitInvoiceResult(
        venta=venta,
        factura=flow_result.get('factura'),
        warnings=flow_result.get('warnings', []),
    )
