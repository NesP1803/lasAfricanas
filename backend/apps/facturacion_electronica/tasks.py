import logging

from django.db import transaction
from django.utils import timezone

from apps.facturacion_electronica.models import FacturaElectronica
from apps.facturacion_electronica.services import FactusClient, build_payload_from_venta
from apps.facturacion_electronica.services.factus_client import FactusAPIError
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def enviar_factura_electronica_task(venta_id: int):
    venta = Venta.objects.select_related('cliente').prefetch_related('detalles__producto').get(pk=venta_id)

    factura_electronica = FacturaElectronica.objects.select_for_update().get(venta=venta)
    if factura_electronica.estado == FacturaElectronica.Estado.ACEPTADA_DIAN:
        logger.info('Factura %s ya aceptada por DIAN, no se reenvía', factura_electronica.reference_code)
        return factura_electronica

    client = FactusClient()
    payload = build_payload_from_venta(venta)

    with transaction.atomic():
        factura_electronica.estado = FacturaElectronica.Estado.ENVIANDO
        factura_electronica.payload = payload
        factura_electronica.marcar_intento()
        factura_electronica.save(update_fields=['estado', 'payload', 'intentos_envio', 'ultimo_intento_at', 'updated_at'])

    try:
        response = client.create_invoice(payload)
    except FactusAPIError as exc:
        with transaction.atomic():
            factura_electronica.estado = FacturaElectronica.Estado.ERROR_API
            factura_electronica.respuesta_api = {'error': str(exc)}
            factura_electronica.save(update_fields=['estado', 'respuesta_api', 'updated_at'])
        logger.exception('Error enviando factura %s a Factus', factura_electronica.reference_code)
        return factura_electronica

    status = str(response.get('status', '')).upper()
    dian_accepted = 'ACEPT' in status or bool(response.get('cufe'))

    with transaction.atomic():
        factura_electronica.respuesta_api = response
        factura_electronica.uuid_factus = response.get('uuid', '')
        factura_electronica.cufe = response.get('cufe', '')
        factura_electronica.enviada_at = timezone.now()
        if dian_accepted:
            factura_electronica.estado = FacturaElectronica.Estado.ACEPTADA_DIAN
            factura_electronica.aceptada_at = timezone.now()
        else:
            factura_electronica.estado = FacturaElectronica.Estado.RECHAZADA_DIAN
        factura_electronica.save(
            update_fields=[
                'estado',
                'respuesta_api',
                'uuid_factus',
                'cufe',
                'enviada_at',
                'aceptada_at',
                'updated_at',
            ]
        )

    return factura_electronica
