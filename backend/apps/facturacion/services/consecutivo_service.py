"""Servicios para control de consecutivos internos DIAN.

Importante de dominio:
- Este módulo gestiona exclusivamente la numeración electrónica (Factus/DIAN).
- NO debe usarse para recalcular/modificar números históricos de documentos ya emitidos.
- Los consecutivos visibles locales (p. ej. FAC-1 / REM-1 en configuración POS) pertenecen
  a configuración local y están desacoplados del ``number`` electrónico de Factus.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.facturacion.models import RangoNumeracionDIAN
from apps.facturacion.services.factus_environment import resolve_factus_environment
from apps.facturacion.services.factus_client import FactusValidationError


DOCUMENT_LABELS = {
    'FACTURA_VENTA': 'factura de venta',
    'NOTA_CREDITO': 'nota crédito',
    'DOCUMENTO_SOPORTE': 'documento soporte',
    'NOTA_AJUSTE_DOCUMENTO_SOPORTE': 'nota de ajuste de documento soporte',
    'NOTA_DEBITO': 'nota débito',
    'REMISION': 'remisión',
}


@dataclass
class InvoiceSequence:
    number: str
    numbering_range_id: int


def resolve_numbering_range(document_code: str = 'FACTURA_VENTA') -> RangoNumeracionDIAN:
    """Resuelve el rango DIAN activo para una NUEVA emisión electrónica.

    No debe invocarse para relinkear facturas históricas ya emitidas.
    """
    document_label = DOCUMENT_LABELS.get(document_code, document_code)
    environment = resolve_factus_environment()
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
            f'Hay múltiples rangos seleccionados localmente para {document_label}. Debe dejar solo uno seleccionado.'
        )
    if selected.count() == 1:
        selected_range = selected.first()
        if not selected_range.activo:
            raise FactusValidationError(
                f'El rango seleccionado para {document_label} está inactivo localmente. Active o seleccione otro rango.'
            )
        if not (selected_range.factus_id or selected_range.factus_range_id):
            raise FactusValidationError(
                f'El rango local seleccionado para {document_label} no tiene ID de Factus (numbering_range_id). '
                'Debe seleccionar/importar un rango autorizado asociado al software antes de emitir.'
            )
        if selected_range.is_expired_remote:
            raise FactusValidationError(
                f'El rango local seleccionado para {document_label} está vencido. Seleccione otro rango vigente.'
            )
        return selected_range

    active_ranges = list(base_queryset.filter(activo=True, is_expired_remote=False).order_by('id'))
    if not active_ranges:
        env_label = 'sandbox' if environment == 'SANDBOX' else 'producción'
        raise FactusValidationError(
            f'No hay rangos sincronizados para {document_label} en {env_label}. Debe sincronizar/configurar el rango antes de emitir.'
        )
    if len(active_ranges) == 1:
        unique_active = active_ranges[0]
        if not (unique_active.factus_id or unique_active.factus_range_id):
            raise FactusValidationError(
                f'El único rango activo para {document_label} no tiene ID de Factus (numbering_range_id). '
                'Debe sincronizar/importar un rango autorizado antes de emitir.'
            )
        if not unique_active.is_selected_local:
            base_queryset.filter(is_selected_local=True).update(is_selected_local=False)
            unique_active.is_selected_local = True
            unique_active.save(update_fields=['is_selected_local'])
        return unique_active

    raise FactusValidationError(
        f'Hay múltiples rangos activos para {document_label} y ninguno está seleccionado. '
        'Seleccione explícitamente un rango antes de emitir.'
    )


def get_next_document_sequence(document_code: str) -> InvoiceSequence:
    """Obtiene e incrementa consecutivo DIAN solo para documentos NUEVOS.

    Este método nunca debe aplicarse a facturas históricas ya emitidas.
    """
    with transaction.atomic():
        range_base = resolve_numbering_range(document_code=document_code)
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
        numbering_range_id=int(rango.factus_range_id or rango.factus_id or 0),
    )


def get_next_invoice_sequence() -> InvoiceSequence:
    return get_next_document_sequence('FACTURA_VENTA')


def get_next_credit_note_sequence() -> InvoiceSequence:
    return get_next_document_sequence('NOTA_CREDITO')


def get_next_support_document_sequence() -> InvoiceSequence:
    return get_next_document_sequence('DOCUMENTO_SOPORTE')


def get_next_support_adjustment_sequence() -> InvoiceSequence:
    return get_next_document_sequence('NOTA_AJUSTE_DOCUMENTO_SOPORTE')


def get_next_invoice_number() -> str:
    return get_next_invoice_sequence().number
