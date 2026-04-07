"""Resolución de rangos DIAN oficiales sincronizados desde Factus."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FactusNumberingRange
from apps.facturacion.services.factus_client import FactusValidationError


@dataclass
class InvoiceSequence:
    number: str
    numbering_range_id: int | None


def resolve_numbering_range(document_code: str = 'FACTURA_VENTA') -> FactusNumberingRange:
    today = timezone.now().date()

    if not FactusNumberingRange.objects.exists():
        raise FactusValidationError('No hay rangos sincronizados con Factus')

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
            'No hay rangos DIAN asociados al software en Factus. Debe sincronizar.'
        )

    return rango


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
