from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from apps.core.models import ConfiguracionFacturacion
from .models import Venta, DetalleVenta, AuditoriaDescuento


@receiver(pre_save, sender=Venta)
def generar_numero_comprobante(sender, instance, **kwargs):
    """Genera número de comprobante automáticamente"""
    if not instance.numero_comprobante:
        if instance.tipo_comprobante == 'FACTURA' and instance.estado != 'COBRADA':
            return
        fecha = timezone.now()
        config = ConfiguracionFacturacion.objects.order_by('-id').first()
        prefijo = {
            'COTIZACION': (getattr(config, 'prefijo_cotizacion', None) or 'COT').strip(),
            'REMISION': (getattr(config, 'prefijo_remision', None) or 'REM').strip(),
            'FACTURA': 'FAC',
        }[instance.tipo_comprobante]
        base = 100000 if instance.tipo_comprobante == 'FACTURA' else 150000
        if instance.tipo_comprobante in {'COTIZACION', 'REMISION'} and config:
            with transaction.atomic():
                locked = ConfiguracionFacturacion.objects.select_for_update().get(pk=config.pk)
                if instance.tipo_comprobante == 'REMISION':
                    nuevo_num = int(locked.numero_remision or 1)
                    locked.numero_remision = nuevo_num + 1
                    locked.save(update_fields=['numero_remision'])
                else:
                    nuevo_num = int(getattr(locked, 'numero_cotizacion', 1) or 1)
                    locked.numero_cotizacion = nuevo_num + 1
                    locked.save(update_fields=['numero_cotizacion'])
        else:
            nuevo_num = Venta.obtener_siguiente_numero(instance.tipo_comprobante, fecha, prefijo, base)
        instance.numero_comprobante = f"{prefijo}-{nuevo_num}"


@receiver(post_save, sender=Venta)
def registrar_auditoria_descuento(sender, instance, created, **kwargs):
    """Registra auditoría si hay descuento aplicado"""
    if created and instance.descuento_porcentaje > 0:
        perfil = instance.vendedor.perfil_vendedor if hasattr(instance.vendedor, 'perfil_vendedor') else None
        descuento_permitido = perfil.descuento_maximo if perfil else 0
        
        AuditoriaDescuento.objects.create(
            venta=instance,
            vendedor=instance.vendedor,
            descuento_solicitado=instance.descuento_porcentaje,
            descuento_permitido=descuento_permitido,
            requirio_aprobacion=instance.descuento_requiere_aprobacion,
            aprobado_por=instance.descuento_aprobado_por
        )
