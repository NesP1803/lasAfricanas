"""Servicio de emisión de documento soporte electrónico vía Factus."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.facturacion.models import DocumentoSoporteElectronico
from apps.facturacion.services.facturar_venta import map_factus_status
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.support_document_payload_builder import build_support_document_payload


def _extract_support_document_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    support_document = data.get('support_document', data)
    return {
        'cufe': str(support_document.get('cufe', '')).strip(),
        'uuid': str(support_document.get('uuid', '')).strip(),
        'number': str(support_document.get('number', '')).strip(),
        'xml_url': str(support_document.get('xml_url', '')).strip(),
        'pdf_url': str(support_document.get('pdf_url', '')).strip(),
        'status': map_factus_status(response_json)[0],
    }


def emitir_documento_soporte(data: dict[str, Any]) -> DocumentoSoporteElectronico:
    payload = build_support_document_payload(data)
    response_json = FactusClient().create_and_validate_support_document(payload)
    fields = _extract_support_document_data(response_json)

    with transaction.atomic():
        documento = DocumentoSoporteElectronico.objects.create(
            number=fields['number'] or str(data.get('number', 'DS-PENDIENTE')).strip(),
            proveedor_nombre=str(data.get('proveedor_nombre', '')).strip(),
            proveedor_documento=str(data.get('proveedor_documento', '')).strip(),
            proveedor_tipo_documento=str(data.get('proveedor_tipo_documento', '')).strip(),
            cufe=fields['cufe'] or None,
            uuid=fields['uuid'] or None,
            status=fields['status'],
            xml_url=fields['xml_url'] or None,
            pdf_url=fields['pdf_url'] or None,
            response_json=response_json,
        )
    return documento
