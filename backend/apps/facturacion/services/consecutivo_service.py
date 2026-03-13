"""Servicios para control de consecutivos internos DIAN."""

from __future__ import annotations

from django.db import transaction

from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_client import FactusValidationError


def get_next_invoice_number() -> str:
    """Obtiene e incrementa el siguiente consecutivo de factura del rango activo."""
    with transaction.atomic():
        rango = (
            RangoNumeracionDIAN.objects.select_for_update()
            .filter(activo=True)
            .order_by('id')
            .first()
        )
        if rango is None:
            raise FactusValidationError('No hay un rango DIAN activo configurado para facturación.')

        siguiente = rango.consecutivo_actual
        if siguiente > rango.hasta:
            raise FactusValidationError(
                f'El rango DIAN activo {rango.prefijo} llegó a su límite ({rango.hasta}).'
            )

        rango.consecutivo_actual = siguiente + 1
        rango.save(update_fields=['consecutivo_actual'])

    return f'{rango.prefijo}{siguiente:06d}'
