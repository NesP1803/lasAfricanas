"""Servicio para consultar y sincronizar el estado DIAN de una factura en Factus."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.electronic_state_machine import map_factus_status
from apps.facturacion.services.exceptions import FacturaNoEncontrada, FactusConsultaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient

logger = logging.getLogger(__name__)

def _extract_bill_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    estado_electronico, estado_factus_raw = map_factus_status(response_json)
    return {
        'cufe': str(bill.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid', '')).strip(),
        'status': estado_electronico,
        'estado_factus_raw': estado_factus_raw,
        'xml_url': str(bill.get('xml_url', '')).strip(),
        'pdf_url': str(bill.get('pdf_url', '')).strip(),
        'codigo_error': str(response_json.get('error_code', '')).strip(),
        'mensaje_error': str(response_json.get('error_message', '')).strip(),
    }


def sync_invoice_status(numero_factura: str) -> FacturaElectronica:
    logger.info('consulta_factura numero=%s', numero_factura)

    factura = FacturaElectronica.objects.filter(number=numero_factura).first()
    if factura is None:
        logger.warning('error_consulta_factura numero=%s detalle=factura_no_encontrada', numero_factura)
        raise FacturaNoEncontrada(f'No existe factura con número {numero_factura}.')

    client = FactusClient()
    try:
        response_json = client.get_invoice(numero_factura)
    except FactusAPIError as exc:
        if getattr(exc, 'status_code', None) == 404:
            logger.info(
                'consulta_factura.no_encontrada_en_factus numero=%s; se conserva estado local',
                numero_factura,
            )
            with transaction.atomic():
                factura.estado_electronico = factura.estado_electronico or 'PENDIENTE_REINTENTO'
                factura.codigo_error = 'FACTUS_DOCUMENTO_NO_ENCONTRADO'
                factura.mensaje_error = (
                    'Factus aún no reporta el documento para este número; intente sincronizar nuevamente en unos minutos.'
                )
                existing_response = factura.response_json if isinstance(factura.response_json, dict) else {}
                factura.response_json = {
                    **existing_response,
                    'sync_estado': 'REMOTE_NOT_FOUND',
                    'sync_numero': numero_factura,
                    'sync_error_detail': str(exc),
                }
                factura.save(
                    update_fields=[
                        'status',
                        'estado_electronico',
                        'codigo_error',
                        'mensaje_error',
                        'response_json',
                        'updated_at',
                    ]
                )
            return factura
        logger.exception('error_consulta_factura numero=%s', numero_factura)
        raise FactusConsultaError('No fue posible consultar el estado de la factura en Factus.') from exc
    except FactusAuthError as exc:
        logger.exception('error_consulta_factura numero=%s', numero_factura)
        raise FactusConsultaError('No fue posible consultar el estado de la factura en Factus.') from exc

    payload = _extract_bill_data(response_json)

    with transaction.atomic():
        factura.cufe = payload['cufe'] or factura.cufe
        factura.uuid = payload['uuid'] or factura.uuid
        factura.estado_electronico = payload['status']
        factura.estado_factus_raw = payload['estado_factus_raw']
        factura.xml_url = payload['xml_url'] or factura.xml_url
        factura.pdf_url = payload['pdf_url'] or factura.pdf_url
        factura.codigo_error = payload['codigo_error'] or None
        factura.mensaje_error = payload['mensaje_error'] or None
        factura.response_json = response_json
        factura.ultima_sincronizacion_at = timezone.now()
        factura.save(
            update_fields=[
                'cufe',
                'uuid',
                'status',
                'estado_electronico',
                'estado_factus_raw',
                'xml_url',
                'pdf_url',
                'codigo_error',
                'mensaje_error',
                'response_json',
                'ultima_sincronizacion_at',
                'updated_at',
            ]
        )

    logger.info('sincronizacion_estado numero=%s estado=%s', factura.number, factura.estado_electronico)
    return factura
