"""Servicio de emisión de notas crédito electrónicas vía Factus."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.facturacion.exceptions import FacturaNoValidaParaNotaCredito
from apps.facturacion.models import FacturaElectronica, NotaCreditoElectronica
from apps.facturacion.services.credit_note_payload_builder import build_credit_note_payload
from apps.facturacion.services.facturar_venta import map_factus_status
from apps.facturacion.services.factus_client import FactusClient, FactusValidationError


def _extract_credit_note_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    credit_note = data.get('credit_note', data)
    return {
        'cufe': str(credit_note.get('cufe', '')).strip(),
        'uuid': str(credit_note.get('uuid', '')).strip(),
        'number': str(credit_note.get('number', '')).strip(),
        'xml_url': str(credit_note.get('xml_url', '')).strip(),
        'pdf_url': str(credit_note.get('pdf_url', '')).strip(),
        'status': map_factus_status(response_json),
    }


def emitir_nota_credito(factura_id: int, motivo: str, items: list[dict[str, Any]]) -> NotaCreditoElectronica:
    factura = FacturaElectronica.objects.filter(pk=factura_id).first()
    if factura is None:
        raise FacturaElectronica.DoesNotExist(f'No existe factura electrónica id={factura_id}.')
    if factura.status != 'ACEPTADA':
        raise FacturaNoValidaParaNotaCredito('La factura debe estar en estado ACEPTADA para emitir nota crédito.')
    if not items:
        raise FactusValidationError('La nota crédito debe contener al menos un ítem.')

    payload = build_credit_note_payload(factura=factura, motivo=motivo, items=items)
    response_json = FactusClient().send_credit_note(payload)
    fields = _extract_credit_note_data(response_json)

    with transaction.atomic():
        nota_credito = NotaCreditoElectronica.objects.create(
            factura=factura,
            number=fields['number'] or f'NC-{factura.number}-{factura.notas_credito.count() + 1}',
            cufe=fields['cufe'] or None,
            uuid=fields['uuid'] or None,
            status=fields['status'],
            xml_url=fields['xml_url'] or None,
            pdf_url=fields['pdf_url'] or None,
            response_json=response_json,
        )
    return nota_credito
