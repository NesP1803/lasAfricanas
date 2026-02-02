from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Venta, DetalleVenta, AuditoriaDescuento


@receiver(pre_save, sender=Venta)
def generar_numero_comprobante(sender, instance, **kwargs):
    """Genera número de comprobante automáticamente"""
    if not instance.numero_comprobante:
        if instance.tipo_comprobante == 'FACTURA' and instance.estado != 'FACTURADA':
            return
        fecha = timezone.now()
        prefijo = {
            'COTIZACION': 'COT',
            'REMISION': 'REM',
            'FACTURA': 'FAC'
        }[instance.tipo_comprobante]
        base = 100000 if instance.tipo_comprobante == 'FACTURA' else 150000
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
