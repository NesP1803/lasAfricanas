"""Máquina de estados para factura electrónica en Factus."""

from __future__ import annotations

from typing import Any

ELECTRONIC_ACTIONS: dict[str, list[str]] = {
    'ACEPTADA': ['descargar_pdf_xml', 'reenviar_correo', 'ver_detalle'],
    'ACEPTADA_CON_OBSERVACIONES': ['descargar_pdf_xml', 'reenviar_correo', 'ver_detalle', 'ver_observaciones'],
    'RECHAZADA': ['ver_errores', 'corregir_datos', 'reintentar_emision'],
    'ERROR_INTEGRACION': ['reintentar_emision', 'ver_detalle_tecnico'],
    'ERROR_PERSISTENCIA': ['sincronizar_factus', 'reparar_persistencia', 'ver_detalle_tecnico'],
    'PENDIENTE_REINTENTO': ['reintentar_ahora', 'ver_historial_intentos'],
}


def extract_bill_errors(response_json: dict[str, Any]) -> list[str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    errors = bill.get('errors', data.get('errors', []))
    if isinstance(errors, str):
        return [errors]
    if not isinstance(errors, list):
        return []
    normalized: list[str] = []
    for item in errors:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict):
            code = str(item.get('code', '')).strip()
            message = str(item.get('message', '')).strip()
            text = ' - '.join(part for part in [code, message] if part)
            if text:
                normalized.append(text)
    return normalized


def map_factus_status(response_json: dict[str, Any]) -> tuple[str, str]:
    """Retorna (estado_electronico, estado_factus_raw)."""
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    status = str(bill.get('status', data.get('status', response_json.get('status', 'error')))).strip().lower()
    number = str(bill.get('number') or data.get('number', '')).strip()
    cufe = str(bill.get('cufe') or data.get('cufe', '')).strip()
    bill_errors = extract_bill_errors(response_json)

    if number and cufe:
        if bill_errors:
            return 'ACEPTADA_CON_OBSERVACIONES', status or 'issued_with_observations'
        return 'ACEPTADA', status or 'issued'
    if status == 'rejected' or bill_errors:
        return 'RECHAZADA', status or 'rejected'
    return 'PENDIENTE_REINTENTO', status or 'pending'


def resolve_actions(estado_electronico: str) -> list[str]:
    return ELECTRONIC_ACTIONS.get(estado_electronico, ['ver_detalle_tecnico'])
