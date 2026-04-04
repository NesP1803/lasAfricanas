"""Resolución estable de URL pública DIAN/Factus."""

from __future__ import annotations

import re
from typing import Any

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.facturar_venta import DOCUMENT_CONCILIATION_ERROR_CODE

_URL_PATTERN = re.compile(r'https?://[^\s<>"]+')


def _extract_url_from_text(raw: str) -> str:
    if not raw:
        return ''
    match = _URL_PATTERN.search(raw)
    return match.group(0).strip() if match else ''


def resolve_public_invoice_url(factura: FacturaElectronica) -> str:
    """Prioriza URL persistida y aplica fallback estable desde payloads persistidos."""
    if not can_expose_public_invoice_url(factura):
        return ''

    public_url = str(factura.public_url or '').strip()
    if public_url:
        return public_url

    response_json: dict[str, Any] = factura.response_json if isinstance(factura.response_json, dict) else {}
    final_fields = response_json.get('final_fields', {}) if isinstance(response_json.get('final_fields', {}), dict) else {}
    data = response_json.get('data', {}) if isinstance(response_json.get('data', {}), dict) else {}
    bill = data.get('bill', {}) if isinstance(data.get('bill', {}), dict) else {}

    candidates = [
        final_fields.get('public_url', ''),
        bill.get('public_url', ''),
        data.get('public_url', ''),
        response_json.get('public_url', ''),
    ]
    for candidate in candidates:
        value = str(candidate or '').strip()
        if value:
            return value

    qr_candidates = [
        str(factura.qr_data or '').strip(),
        str(final_fields.get('qr', '') or '').strip(),
        str(bill.get('qr', '') or '').strip(),
        str(data.get('qr', '') or '').strip(),
    ]
    for candidate in qr_candidates:
        extracted = _extract_url_from_text(candidate)
        if extracted:
            return extracted

    return ''


def has_documental_inconsistency(factura: FacturaElectronica) -> bool:
    codigo_error = str(factura.codigo_error or '').strip()
    mensaje_error = str(factura.mensaje_error or '').strip()
    return codigo_error == DOCUMENT_CONCILIATION_ERROR_CODE or DOCUMENT_CONCILIATION_ERROR_CODE in mensaje_error


def can_expose_public_invoice_url(factura: FacturaElectronica) -> bool:
    status = str(factura.estado_electronico or factura.status or '').strip()
    return status in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'} and not has_documental_inconsistency(factura)
