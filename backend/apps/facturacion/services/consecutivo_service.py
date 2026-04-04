"""Servicios para control de consecutivos internos DIAN."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_client import FactusValidationError


def _current_environment() -> str:
    raw = str(getattr(settings, 'FACTUS_ENV', 'sandbox')).strip().lower()
    return 'PRODUCTION' if raw in {'prod', 'production'} else 'SANDBOX'


@dataclass
class InvoiceSequence:
    number: str
    numbering_range_id: int


def resolve_numbering_range(document_code: str = 'FACTURA_VENTA') -> RangoNumeracionDIAN:
    document_label = 'factura' if document_code == 'FACTURA_VENTA' else 'nota crédito'
    environment = _current_environment()
    base_queryset = RangoNumeracionDIAN.objects.filter(
        environment=environment,
        document_code=document_code,
    )
    if not base_queryset.exists():
        env_label = 'sandbox' if environment == 'SANDBOX' else 'producción'
        raise FactusValidationError(
            f'No hay rangos sincronizados para {document_label} en {env_label}. Debe sincronizar/configurar el rango antes de emitir.'
        )

    selected = base_queryset.filter(is_selected_local=True)
    if selected.count() > 1:
        raise FactusValidationError(
            f'Hay múltiples rangos seleccionados localmente para {document_label}. Debe dejar solo uno activo.'
        )
    if selected.count() == 1:
        selected_range = selected.first()
        if not selected_range.is_active_remote:
            env_label = 'producción' if environment == 'PRODUCTION' else 'sandbox'
            raise FactusValidationError(
                f'No hay rango local activo configurado para {document_label} en {env_label}. Debe sincronizar/configurar el rango antes de emitir.'
            )
        return selected_range

    active_ranges = list(base_queryset.filter(is_active_remote=True).order_by('id'))
    if not active_ranges:
        env_label = 'sandbox' if environment == 'SANDBOX' else 'producción'
        raise FactusValidationError(
            f'No hay rangos sincronizados para {document_label} en {env_label}. Debe sincronizar/configurar el rango antes de emitir.'
        )
    if len(active_ranges) == 1:
        return active_ranges[0]

    raise FactusValidationError(
        f'Hay múltiples rangos activos para {document_label}, pero ninguno está seleccionado localmente.'
    )


def get_next_invoice_sequence() -> InvoiceSequence:
    """Obtiene e incrementa el siguiente consecutivo del rango resuelto para factura de venta."""
    with transaction.atomic():
        range_base = resolve_numbering_range(document_code='FACTURA_VENTA')
        rango = RangoNumeracionDIAN.objects.select_for_update().get(pk=range_base.pk)

        siguiente = rango.consecutivo_actual
        if siguiente > rango.hasta:
            raise FactusValidationError(
                f'El rango DIAN activo {rango.prefijo} llegó a su límite ({rango.hasta}).'
            )

        rango.consecutivo_actual = siguiente + 1
        rango.save(update_fields=['consecutivo_actual'])

    return InvoiceSequence(
        number=f'{rango.prefijo}{siguiente:06d}',
        numbering_range_id=int(rango.factus_range_id or 0),
    )


def get_next_invoice_number() -> str:
    return get_next_invoice_sequence().number
