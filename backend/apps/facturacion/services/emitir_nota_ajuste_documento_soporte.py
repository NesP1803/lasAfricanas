"""Servicio de emisión de notas de ajuste para documento soporte vía Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.facturacion.exceptions import DocumentoSoporteNoValido
from apps.facturacion.models import DocumentoSoporteElectronico, NotaAjusteDocumentoSoporte
from apps.facturacion.services.facturar_venta import map_factus_status
from apps.facturacion.services.factus_client import FactusClient, FactusValidationError
from apps.facturacion.services.support_document_adjustment_payload_builder import build_adjustment_payload

logger = logging.getLogger(__name__)


def _extract_adjustment_note_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    adjustment_note = data.get('support_document_adjustment_note', data)
    return {
        'cufe': str(adjustment_note.get('cufe', '')).strip(),
        'uuid': str(adjustment_note.get('uuid', '')).strip(),
        'number': str(adjustment_note.get('number', '')).strip(),
        'xml_url': str(adjustment_note.get('xml_url', '')).strip(),
        'pdf_url': str(adjustment_note.get('pdf_url', '')).strip(),
        'status': map_factus_status(response_json)[0],
    }


def emitir_nota_ajuste_documento_soporte(
    documento_soporte_id: int,
    motivo: str,
    items: list[dict[str, Any]],
) -> NotaAjusteDocumentoSoporte:
    documento_soporte = DocumentoSoporteElectronico.objects.filter(pk=documento_soporte_id).first()
    if documento_soporte is None:
        raise DocumentoSoporteElectronico.DoesNotExist(
            f'No existe documento soporte electrónico id={documento_soporte_id}.'
        )
    if documento_soporte.status != 'ACEPTADA':
        raise DocumentoSoporteNoValido(
            'El documento soporte debe estar en estado ACEPTADA para emitir nota de ajuste.'
        )
    if not items:
        raise FactusValidationError('La nota de ajuste debe contener al menos un ítem.')

    payload = build_adjustment_payload(documento_soporte=documento_soporte, motivo=motivo, items=items)
    logger.info(
        'facturacion.nota_ajuste_documento_soporte.payload.range_selected document_code=%s numbering_range_id=%s support_document_id=%s',
        'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        payload.get('numbering_range_id'),
        documento_soporte_id,
    )
    response_json = FactusClient().send_support_document_adjustment(payload)
    fields = _extract_adjustment_note_data(response_json)

    with transaction.atomic():
        nota_ajuste = NotaAjusteDocumentoSoporte.objects.create(
            documento_soporte=documento_soporte,
            number=(
                fields['number']
                or f'NAS-{documento_soporte.number}-{documento_soporte.notas_ajuste.count() + 1}'
            ),
            cufe=fields['cufe'] or None,
            uuid=fields['uuid'] or None,
            status=fields['status'],
            xml_url=fields['xml_url'] or None,
            pdf_url=fields['pdf_url'] or None,
            response_json=response_json,
        )
    return nota_ajuste
