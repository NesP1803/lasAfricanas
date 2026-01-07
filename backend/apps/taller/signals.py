from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import ServicioMoto, ConsumoRepuesto, RepuestoAsignado


@receiver(pre_save, sender=ServicioMoto)
def generar_numero_servicio(sender, instance, **kwargs):
    """Genera número de servicio automáticamente"""
    if not instance.numero_servicio:
        fecha = timezone.now()
        
        # Buscar el último servicio del mes
        ultimo = ServicioMoto.objects.filter(
            fecha_ingreso__year=fecha.year,
            fecha_ingreso__month=fecha.month
        ).order_by('-numero_servicio').first()
        
        if ultimo and ultimo.numero_servicio:
            try:
                ultimo_num = int(ultimo.numero_servicio.split('-')[-1])
                nuevo_num = ultimo_num + 1
            except (ValueError, IndexError):
                nuevo_num = 1
        else:
            nuevo_num = 1
        
        instance.numero_servicio = f"SRV-{fecha.strftime('%Y%m')}-{nuevo_num:04d}"


@receiver(post_save, sender=ConsumoRepuesto)
def descontar_repuesto(sender, instance, created, **kwargs):
    """
    Descuenta el repuesto del cajón del mecánico o del inventario general.
    Actualiza el total del servicio.
    """
    if created and not instance.stock_descontado:
        mecanico = instance.servicio.mecanico
        producto = instance.producto
        
        # Intentar descontar del cajón del mecánico primero
        try:
            repuesto_asignado = RepuestoAsignado.objects.get(
                mecanico=mecanico,
                producto=producto,
                is_active=True
            )
            
            if repuesto_asignado.cantidad >= instance.cantidad:
                # Descontar del cajón del mecánico
                repuesto_asignado.cantidad -= instance.cantidad
                repuesto_asignado.save()
                instance.descontado_de_mecanico = True
            else:
                # No hay suficiente en el cajón, descontar del inventario general
                if producto.stock >= instance.cantidad:
                    producto.stock -= instance.cantidad
                    producto.save()
                    
                    # Registrar movimiento
                    from apps.inventario.models import MovimientoInventario
                    MovimientoInventario.objects.create(
                        producto=producto,
                        tipo='TALLER',
                        cantidad=-instance.cantidad,
                        stock_anterior=producto.stock + instance.cantidad,
                        stock_nuevo=producto.stock,
                        costo_unitario=instance.precio_unitario,
                        usuario=instance.registrado_por,
                        referencia=f"Servicio {instance.servicio.numero_servicio}",
                        observaciones=f"Consumo taller - {instance.servicio.placa}"
                    )
                    instance.descontado_de_mecanico = False
                else:
                    # No hay stock suficiente
                    pass  # Manejar este caso según tu lógica de negocio
        
        except RepuestoAsignado.DoesNotExist:
            # El mecánico no tiene este repuesto asignado, descontar del inventario
            if producto.stock >= instance.cantidad:
                producto.stock -= instance.cantidad
                producto.save()
                
                # Registrar movimiento
                from apps.inventario.models import MovimientoInventario
                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='TALLER',
                    cantidad=-instance.cantidad,
                    stock_anterior=producto.stock + instance.cantidad,
                    stock_nuevo=producto.stock,
                    costo_unitario=instance.precio_unitario,
                    usuario=instance.registrado_por,
                    referencia=f"Servicio {instance.servicio.numero_servicio}",
                    observaciones=f"Consumo taller - {instance.servicio.placa}"
                )
                instance.descontado_de_mecanico = False
        
        instance.stock_descontado = True
        instance.save(update_fields=['stock_descontado', 'descontado_de_mecanico'])
        
        # Actualizar total del servicio
        servicio = instance.servicio
        servicio.calcular_total()
        servicio.save(update_fields=['costo_repuestos', 'total', 'updated_at'])


@receiver(post_save, sender=ServicioMoto)
def actualizar_estado_entrega(sender, instance, **kwargs):
    """Registra la fecha de entrega real cuando el estado cambia a ENTREGADO"""
    if instance.estado == 'ENTREGADO' and not instance.fecha_entrega_real:
        instance.fecha_entrega_real = timezone.now()
        instance.save(update_fields=['fecha_entrega_real'])