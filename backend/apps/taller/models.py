from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from decimal import Decimal


class Mecanico(BaseModel):
    """
    Mecánicos del taller.
    Sistema de 'cajones' por mecánico con repuestos asociados.
    """
    usuario = models.OneToOneField(
        'usuarios.Usuario',
        on_delete=models.CASCADE,
        related_name='mecanico',
        verbose_name='Usuario'
    )
    especialidad = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Especialidad',
        help_text='Ej: Electricidad, Motor, Suspensión'
    )
    comision_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='Comisión (%)',
        help_text='Porcentaje de comisión sobre servicios'
    )
    
    class Meta:
        db_table = 'mecanicos'
        verbose_name = 'Mecánico'
        verbose_name_plural = 'Mecánicos'
        ordering = ['usuario__first_name', 'usuario__last_name']
    
    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username
    
    @property
    def total_cuentas(self):
        """Total de dinero en repuestos asignados al mecánico"""
        from django.db.models import Sum, F
        total = self.repuestos_asignados.filter(
            is_active=True
        ).aggregate(
            total=Sum(F('cantidad') * F('precio_unitario'))
        )['total'] or Decimal('0.00')
        return total
    
    @property
    def servicios_activos(self):
        """Cantidad de servicios activos del mecánico"""
        return self.servicios.filter(
            estado__in=['INGRESADO', 'EN_DIAGNOSTICO', 'EN_REPARACION']
        ).count()


class ServicioMoto(BaseModel):
    """
    Servicios de motos en el taller.
    Registro completo del ciclo de vida del servicio.
    """
    ESTADO = [
        ('INGRESADO', 'Ingresado'),
        ('EN_DIAGNOSTICO', 'En Diagnóstico'),
        ('COTIZADO', 'Cotizado'),
        ('APROBADO', 'Aprobado por Cliente'),
        ('EN_REPARACION', 'En Reparación'),
        ('TERMINADO', 'Terminado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    # Identificación del servicio
    numero_servicio = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        verbose_name='Número de servicio'
    )
    
    # Información de la moto
    placa = models.CharField(
        max_length=10,
        db_index=True,
        verbose_name='Placa'
    )
    marca = models.CharField(
        max_length=100,
        verbose_name='Marca'
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Modelo'
    )
    color = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Color'
    )
    
    # Cliente
    cliente = models.ForeignKey(
        'ventas.Cliente',
        on_delete=models.PROTECT,
        related_name='servicios_taller',
        verbose_name='Cliente'
    )
    
    # Asignación
    mecanico = models.ForeignKey(
        Mecanico,
        on_delete=models.PROTECT,
        related_name='servicios',
        verbose_name='Mecánico asignado'
    )
    recibido_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='servicios_recibidos',
        verbose_name='Recibido por'
    )
    
    # Fechas
    fecha_ingreso = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Fecha de ingreso'
    )
    fecha_estimada_entrega = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha estimada de entrega'
    )
    fecha_entrega_real = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de entrega real'
    )
    
    # Información del servicio
    kilometraje = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Kilometraje'
    )
    nivel_gasolina = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Nivel de gasolina',
        help_text='1/4, 1/2, 3/4, Lleno, Vacío'
    )
    observaciones_ingreso = models.TextField(
        verbose_name='Observaciones al ingreso',
        help_text='Estado de la moto, daños existentes, etc.'
    )
    diagnostico = models.TextField(
        blank=True,
        verbose_name='Diagnóstico'
    )
    trabajo_realizado = models.TextField(
        blank=True,
        verbose_name='Trabajo realizado'
    )
    recomendaciones = models.TextField(
        blank=True,
        verbose_name='Recomendaciones'
    )
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO,
        default='INGRESADO',
        db_index=True,
        verbose_name='Estado'
    )
    
    # Costos
    costo_mano_obra = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Costo mano de obra'
    )
    costo_repuestos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Costo repuestos',
        help_text='Se calcula automáticamente'
    )
    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Descuento'
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        db_index=True,
        verbose_name='Total'
    )
    
    # Facturación
    venta = models.OneToOneField(
        'ventas.Venta',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='servicio_taller',
        verbose_name='Venta asociada'
    )
    
    class Meta:
        db_table = 'servicios_moto'
        verbose_name = 'Servicio de Moto'
        verbose_name_plural = 'Servicios de Motos'
        ordering = ['-fecha_ingreso']
        indexes = [
            models.Index(fields=['numero_servicio']),
            models.Index(fields=['placa']),
            models.Index(fields=['estado', 'fecha_ingreso']),
            models.Index(fields=['mecanico', 'estado']),
            models.Index(fields=['cliente', 'fecha_ingreso']),
        ]
    
    def __str__(self):
        return f"{self.numero_servicio} - {self.placa}"

    def save(self, *args, **kwargs):
        """Genera número de servicio automáticamente si no existe"""
        if not self.numero_servicio:
            from datetime import datetime
            # Generar número: SRV-YYYYMMDD-NNNN
            fecha = datetime.now().strftime('%Y%m%d')
            ultimo_servicio = ServicioMoto.objects.filter(
                numero_servicio__startswith=f'SRV-{fecha}'
            ).order_by('-numero_servicio').first()

            if ultimo_servicio:
                ultimo_num = int(ultimo_servicio.numero_servicio.split('-')[-1])
                nuevo_num = ultimo_num + 1
            else:
                nuevo_num = 1

            self.numero_servicio = f'SRV-{fecha}-{nuevo_num:04d}'

        super().save(*args, **kwargs)

    def calcular_total(self):
        """Calcula el total del servicio"""
        # Sumar todos los repuestos consumidos
        self.costo_repuestos = sum(
            consumo.subtotal 
            for consumo in self.consumos_repuestos.filter(is_active=True)
        )
        
        # Calcular total
        self.total = self.costo_mano_obra + self.costo_repuestos - self.descuento
        return self.total
    
    def puede_facturar(self):
        """Verifica si el servicio puede ser facturado"""
        if self.venta:
            return False, "Este servicio ya tiene una factura asociada"
        
        if self.estado not in ['TERMINADO', 'ENTREGADO']:
            return False, "El servicio debe estar terminado para facturar"
        
        return True, "OK"


class RepuestoAsignado(BaseModel):
    """
    Repuestos asignados al 'cajón' de cada mecánico.
    Sistema de inventario por mecánico.
    """
    mecanico = models.ForeignKey(
        Mecanico,
        on_delete=models.CASCADE,
        related_name='repuestos_asignados',
        verbose_name='Mecánico'
    )
    producto = models.ForeignKey(
        'inventario.Producto',
        on_delete=models.PROTECT,
        related_name='asignaciones_mecanico',
        verbose_name='Producto'
    )
    cantidad = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Cantidad'
    )
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Precio unitario'
    )
    fecha_asignacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de asignación'
    )
    
    class Meta:
        db_table = 'repuestos_asignados'
        verbose_name = 'Repuesto Asignado a Mecánico'
        verbose_name_plural = 'Repuestos Asignados a Mecánicos'
        unique_together = ['mecanico', 'producto']
        ordering = ['-fecha_asignacion']
    
    def __str__(self):
        return f"{self.producto.codigo} - {self.mecanico} ({self.cantidad} und)"
    
    @property
    def valor_total(self):
        """Valor total de este repuesto asignado"""
        return self.cantidad * self.precio_unitario


class ConsumoRepuesto(BaseModel):
    """
    Repuestos consumidos en un servicio específico.
    Descuenta del cajón del mecánico o del inventario general.
    """
    servicio = models.ForeignKey(
        ServicioMoto,
        on_delete=models.CASCADE,
        related_name='consumos_repuestos',
        verbose_name='Servicio'
    )
    producto = models.ForeignKey(
        'inventario.Producto',
        on_delete=models.PROTECT,
        related_name='consumos_taller',
        verbose_name='Producto'
    )
    cantidad = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad'
    )
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Precio unitario'
    )
    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Descuento'
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Subtotal'
    )
    
    # Control
    registrado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        verbose_name='Registrado por'
    )
    descontado_de_mecanico = models.BooleanField(
        default=False,
        verbose_name='Descontado del cajón del mecánico',
        help_text='Si se descontó del cajón del mecánico o del inventario general'
    )
    stock_descontado = models.BooleanField(
        default=False,
        verbose_name='Stock descontado',
        help_text='Si ya se descontó del inventario'
    )
    
    class Meta:
        db_table = 'consumos_repuestos_taller'
        verbose_name = 'Consumo de Repuesto en Taller'
        verbose_name_plural = 'Consumos de Repuestos en Taller'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['servicio']),
            models.Index(fields=['producto']),
        ]
    
    def __str__(self):
        return f"{self.producto.codigo} x{self.cantidad} - {self.servicio.numero_servicio}"
    
    def save(self, *args, **kwargs):
        """Calcula subtotal antes de guardar"""
        self.subtotal = (self.precio_unitario * self.cantidad) - self.descuento
        super().save(*args, **kwargs)