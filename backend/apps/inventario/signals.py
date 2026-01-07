from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MovimientoInventario


@receiver(post_save, sender=MovimientoInventario)
def actualizar_stock_producto(sender, instance, created, **kwargs):
    """
    Actualiza el stock del producto cuando hay un movimiento.
    Este signal se ejecuta DESPUÉS de guardar el movimiento.
    """
    if created:
        # Ya el stock_nuevo se calculó, solo actualizamos el producto
        producto = instance.producto
        producto.stock = instance.stock_nuevo
        producto.save(update_fields=['stock', 'updated_at'])
