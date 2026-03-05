from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.facturacion_electronica.models import FacturaElectronica
from apps.facturacion_electronica.tasks import enviar_factura_electronica_task
from apps.ventas.models import Venta


@receiver(post_save, sender=Venta)
def crear_factura_electronica_al_facturar(sender, instance: Venta, created: bool, **kwargs):
    if instance.estado != 'FACTURADA' or instance.tipo_comprobante != 'FACTURA':
        return

    if not instance.numero_comprobante:
        return

    factura, _ = FacturaElectronica.objects.get_or_create(
        venta=instance,
        defaults={
            'reference_code': instance.numero_comprobante,
            'numbering_range_id': 1,
            'estado': FacturaElectronica.Estado.PENDIENTE,
        },
    )

    if factura.estado == FacturaElectronica.Estado.ACEPTADA_DIAN:
        return

    enviar_factura_electronica_task(instance.id)
