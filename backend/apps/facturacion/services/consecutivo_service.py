"""Resolución de rangos DIAN oficiales sincronizados desde Factus."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.core.models import ConfiguracionFacturacion
from apps.facturacion.models import FactusNumberingRange
from apps.facturacion.services.factus_client import FactusValidationError


@dataclass
class InvoiceSequence:
    number: str
    numbering_range_id: int | None


def resolve_numbering_range(document_code: str = 'FACTURA_VENTA') -> FactusNumberingRange:
    today = timezone.now().date()

    if not FactusNumberingRange.objects.exists():
        raise FactusValidationError(
            'No hay rangos técnicos disponibles en la caché local de Factus para este documento.'
        )

    rango = (
        FactusNumberingRange.objects.filter(
            document=document_code,
            is_active=True,
            end_date__gte=today,
        )
        .order_by('start_date')
        .first()
    )
    if not rango:
        raise FactusValidationError(
            'No hay rangos técnicos vigentes disponibles en Factus para este documento.'
        )

    return rango


def resolve_electronic_numbering_range_id(document_code: str = 'FACTURA_VENTA') -> int:
    """
    Resuelve el identificador técnico del rango electrónico administrado en Factus.

    Fuente única:
    - Configuración técnica explícita (Configuración > Facturación).
    """
    configuracion = ConfiguracionFacturacion.objects.order_by('-id').first()
    field_name = {
        'FACTURA_VENTA': 'factus_numbering_range_id_factura_venta',
        'NOTA_CREDITO': 'factus_numbering_range_id_nota_credito',
    }.get(document_code, '')
    if configuracion and field_name:
        configured_id = int(getattr(configuracion, field_name, 0) or 0)
        if configured_id > 0:
            return configured_id

    raise FactusValidationError(
        'La referencia técnica del rango electrónico configurado en Factus no es válida. '
        'Actualice el identificador técnico del rango activo.'
    )


def get_next_document_sequence(document_code: str) -> InvoiceSequence:
    with transaction.atomic():
        rango = FactusNumberingRange.objects.select_for_update().get(pk=resolve_numbering_range(document_code).pk)
        siguiente = int(rango.from_number)
        rango.from_number = siguiente + 1
        rango.save(update_fields=['from_number'])
    return InvoiceSequence(number=f'{rango.prefix}{siguiente:06d}', numbering_range_id=None)


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
