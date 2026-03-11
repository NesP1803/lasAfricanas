"""Servicios para integración con API Factus."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.db import transaction

from apps.facturacion.models import FacturaElectronica
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


class FactusServiceError(Exception):
    """Error controlado para fallos al comunicarse con Factus."""


def _extract_factus_data(response_json: dict[str, Any]) -> dict[str, str]:
    """Normaliza la estructura de respuesta de Factus para campos persistibles."""
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)

    return {
        'cufe': str(bill.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid', '')).strip(),
        'number': str(bill.get('number', '')).strip(),
        'xml_url': str(bill.get('xml_url', '')).strip(),
        'pdf_url': str(bill.get('pdf_url', '')).strip(),
        'qr': str(bill.get('qr', '')).strip(),
        'status': str(bill.get('status', data.get('status', response_json.get('status', 'UNKNOWN')))).strip(),
    }


def send_invoice_to_factus(venta: Venta, payload: dict[str, Any]) -> FacturaElectronica:
    """Envía una factura a Factus y persiste su trazabilidad.

    Args:
        venta: Instancia de venta a facturar electrónicamente.
        payload: Cuerpo JSON listo para enviar al endpoint de Factus.

    Raises:
        FactusServiceError: Si Factus responde con error o datos incompletos.

    Returns:
        FacturaElectronica: Instancia creada con la respuesta exitosa.
    """
    base_url = getattr(settings, 'FACTUS_API_URL', 'https://api-sandbox.factus.com.co').rstrip('/')
    validate_path = getattr(settings, 'FACTUS_BILLS_VALIDATE_PATH', '/v1/bills/validate')
    bearer_token = getattr(settings, 'FACTUS_BEARER_TOKEN', '')

    if not bearer_token:
        raise FactusServiceError('No se configuró FACTUS_BEARER_TOKEN en settings/env.')

    endpoint = f'{base_url}{validate_path}'
    headers = {
        'Authorization': f'Bearer {bearer_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        response_json = response.json()
    except requests.RequestException as exc:
        logger.exception('Error de red/API al facturar venta=%s en Factus: %s', venta.id, exc)
        raise FactusServiceError('No fue posible comunicarse con Factus.') from exc
    except ValueError as exc:
        logger.exception('Factus devolvió JSON inválido para venta=%s', venta.id)
        raise FactusServiceError('Factus devolvió una respuesta no válida.') from exc

    if response_json.get('error'):
        logger.error('Factus respondió con error para venta=%s: %s', venta.id, response_json)
        raise FactusServiceError('Factus respondió con error al validar la factura.')

    fields = _extract_factus_data(response_json)
    required_fields = ['cufe', 'uuid', 'number', 'xml_url', 'pdf_url', 'qr', 'status']
    missing_fields = [field for field in required_fields if not fields[field]]
    if missing_fields:
        logger.error(
            'Respuesta incompleta de Factus para venta=%s. Campos faltantes: %s. payload=%s',
            venta.id,
            ', '.join(missing_fields),
            response_json,
        )
        raise FactusServiceError('La respuesta de Factus no contiene todos los datos requeridos.')

    with transaction.atomic():
        factura = FacturaElectronica.objects.create(
            venta=venta,
            cufe=fields['cufe'],
            uuid=fields['uuid'],
            number=fields['number'],
            xml_url=fields['xml_url'],
            pdf_url=fields['pdf_url'],
            qr=fields['qr'],
            status=fields['status'],
            response_json=response_json,
        )

    return factura
