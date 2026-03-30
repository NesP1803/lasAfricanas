from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .cerrar_venta import validar_detalles_venta


def enviar_venta_a_caja(venta, user):
    if venta.estado != 'BORRADOR':
        raise ValidationError('Solo se pueden enviar a caja ventas en borrador.')

    if venta.tipo_comprobante != 'FACTURA':
        raise ValidationError('Solo las facturas se pueden enviar a caja.')

    validar_detalles_venta(venta)

    venta.estado = 'ENVIADA_A_CAJA'
    venta.enviada_a_caja_por = user
    venta.enviada_a_caja_at = timezone.now()
    venta.save(
        update_fields=[
            'estado',
            'enviada_a_caja_por',
            'enviada_a_caja_at',
            'updated_at',
        ]
    )

    return venta
