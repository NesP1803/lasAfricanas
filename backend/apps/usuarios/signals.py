from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, PerfilVendedor


@receiver(post_save, sender=Usuario)
def crear_perfil_vendedor(sender, instance, created, **kwargs):
    """
    Signal que crea automáticamente un PerfilVendedor 
    cuando se crea un usuario de tipo VENDEDOR.
    """
    if created and instance.tipo_usuario == 'VENDEDOR':
        PerfilVendedor.objects.create(
            usuario=instance,
            descuento_maximo=5.00,  # Descuento por defecto: 5%
            puede_ver_costo=False,
            puede_eliminar_ventas=False,
            puede_modificar_precios=False,
            comision_porcentaje=0
        )


@receiver(post_save, sender=Usuario)
def guardar_perfil_vendedor(sender, instance, **kwargs):
    """
    Signal que guarda el perfil del vendedor cuando se actualiza el usuario.
    """
    if instance.tipo_usuario == 'VENDEDOR' and hasattr(instance, 'perfil_vendedor'):
        instance.perfil_vendedor.save()