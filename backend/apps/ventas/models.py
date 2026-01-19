from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from decimal import Decimal


class Cliente(BaseModel):
    """Clientes de Las Africanas"""
    TIPO_DOCUMENTO = [
        ('CC', 'Cédula de Ciudadanía'),
        ('NIT', 'NIT'),
        ('CE', 'Cédula de Extranjería'),
        ('PASAPORTE', 'Pasaporte'),
    ]
    
    tipo_documento = models.CharField(
        max_length=50,
        choices=TIPO_DOCUMENTO,
        default='CC',
        verbose_name='Tipo de documento'
    )
    numero_documento = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Número de documento'
    )
    nombre = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name='Nombre completo o razón social'
    )
    telefono = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Teléfono'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='Email'
    )
    direccion = models.TextField(
        blank=True,
        verbose_name='Dirección'
    )
    ciudad = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Ciudad'
    )
    
    class Meta:
        db_table = 'clientes'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['numero_documento']),
            models.Index(fields=['nombre']),
        ]
    
    def __str__(self):
        return f"{self.numero_documento} - {self.nombre}"


class Venta(BaseModel):
    """
    Ventas/Facturas del sistema.
    Maneja 3 tipos: COTIZACION, REMISION, FACTURA
    """
    TIPO_COMPROBANTE = [
        ('COTIZACION', 'Cotización'),
        ('REMISION', 'Remisión'),
        ('FACTURA', 'Factura'),
    ]
    
    ESTADO = [
        ('BORRADOR', 'Borrador'),
        ('CONFIRMADA', 'Confirmada'),
        ('ANULADA', 'Anulada'),
    ]
    
    MEDIO_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('TARJETA', 'Tarjeta'),
        ('CREDITO', 'Crédito'),
    ]
    
    # Tipo de comprobante
    tipo_comprobante = models.CharField(
        max_length=20,
        choices=TIPO_COMPROBANTE,
        default='FACTURA',
        db_index=True,
        verbose_name='Tipo de comprobante'
    )
    
    # Numeración
    numero_comprobante = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Número de comprobante',
        help_text='FAC-100702, REM-154239, COT-001234'
    )
    
    # Relaciones
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='ventas',
        verbose_name='Cliente'
    )
    vendedor = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='ventas',
        verbose_name='Vendedor'
    )
    
    # Fechas
    fecha = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Fecha y hora'
    )
    
    # Totales
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Subtotal'
    )
    descuento_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Descuento (%)'
    )
    descuento_valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Descuento ($)'
    )
    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='IVA'
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_index=True,
        verbose_name='Total a pagar'
    )
    
    # Control de descuentos
    descuento_aprobado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='descuentos_aprobados',
        verbose_name='Descuento aprobado por'
    )
    descuento_requiere_aprobacion = models.BooleanField(
        default=False,
        verbose_name='Requiere aprobación de gerente'
    )
    
    # Pago
    medio_pago = models.CharField(
        max_length=20,
        choices=MEDIO_PAGO,
        default='EFECTIVO',
        verbose_name='Medio de pago'
    )
    efectivo_recibido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Efectivo recibido'
    )
    cambio = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Cambio'
    )
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO,
        default='CONFIRMADA',
        db_index=True,
        verbose_name='Estado'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    
    # Relación con remisión (si es factura que proviene de remisión)
    remision_origen = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='facturas_generadas',
        verbose_name='Remisión de origen',
        help_text='Si esta factura se generó desde una remisión'
    )
    
    # Facturación electrónica (solo para FACTURA)
    factura_electronica_uuid = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name='UUID Factura Electrónica'
    )
    factura_electronica_cufe = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='CUFE'
    )
    fecha_envio_dian = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha envío a DIAN'
    )
    
    class Meta:
        db_table = 'ventas'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['numero_comprobante']),
            models.Index(fields=['tipo_comprobante', 'fecha']),
            models.Index(fields=['vendedor', 'fecha']),
            models.Index(fields=['cliente', 'fecha']),
            models.Index(fields=['estado', 'fecha']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_comprobante_display()} {self.numero_comprobante}"
    
    def clean(self):
        """Validaciones personalizadas"""
        # Solo facturas pueden tener datos de DIAN
        if self.tipo_comprobante != 'FACTURA' and (self.factura_electronica_uuid or self.factura_electronica_cufe):
            raise ValidationError('Solo las facturas pueden tener datos de facturación electrónica')
        
        # Validar descuento con permisos del vendedor
        if hasattr(self.vendedor, 'perfil_vendedor'):
            perfil = self.vendedor.perfil_vendedor
            puede_aplicar, requiere_aprobacion = perfil.puede_aplicar_descuento(self.descuento_porcentaje)
            
            if requiere_aprobacion and not self.descuento_aprobado_por:
                self.descuento_requiere_aprobacion = True
                raise ValidationError(
                    f'El descuento de {self.descuento_porcentaje}% excede el límite de '
                    f'{perfil.descuento_maximo}%. Requiere aprobación del gerente.'
                )
    
    @property
    def afecta_inventario(self):
        """Indica si este tipo de comprobante afecta el inventario"""
        return self.tipo_comprobante in ['REMISION', 'FACTURA']
    
    @property
    def requiere_envio_dian(self):
        """Indica si debe enviarse a DIAN"""
        return self.tipo_comprobante == 'FACTURA'
    
    def convertir_a_factura(self):
        """
        Convierte una REMISIÓN en FACTURA electrónica.
        NO afecta inventario porque ya se descontó en la remisión.
        """
        if self.tipo_comprobante != 'REMISION':
            raise ValueError("Solo remisiones pueden convertirse en facturas")
        
        if self.estado == 'ANULADA':
            raise ValueError("No se puede facturar una remisión anulada")
        
        # Generar número de factura
        from django.utils import timezone
        fecha = timezone.now()
        ultimo = Venta.objects.filter(
            tipo_comprobante='FACTURA',
            fecha__year=fecha.year,
            fecha__month=fecha.month
        ).order_by('-numero_comprobante').first()
        
        if ultimo:
            ultimo_num = int(ultimo.numero_comprobante.split('-')[1])
            nuevo_num = ultimo_num + 1
        else:
            nuevo_num = 100000
        
        numero_factura = f"FAC-{nuevo_num}"
        
        # Crear factura
        factura = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante=numero_factura,
            cliente=self.cliente,
            vendedor=self.vendedor,
            subtotal=self.subtotal,
            descuento_porcentaje=self.descuento_porcentaje,
            descuento_valor=self.descuento_valor,
            iva=self.iva,
            total=self.total,
            medio_pago=self.medio_pago,
            efectivo_recibido=self.efectivo_recibido,
            cambio=self.cambio,
            remision_origen=self,
            observaciones=f"Generada desde remisión {self.numero_comprobante}"
        )
        
        # Copiar detalles (sin afectar inventario de nuevo)
        for detalle in self.detalles.all():
            DetalleVenta.objects.create(
                venta=factura,
                producto=detalle.producto,
                cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario,
                descuento_unitario=detalle.descuento_unitario,
                iva_porcentaje=detalle.iva_porcentaje,
                subtotal=detalle.subtotal,
                total=detalle.total,
                afecto_inventario=False  # Ya se descontó en la remisión
            )
        
        return factura


class DetalleVenta(BaseModel):
    """Detalle de productos/servicios en una venta"""
    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Venta'
    )
    producto = models.ForeignKey(
        'inventario.Producto',
        on_delete=models.PROTECT,
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
    descuento_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Descuento por unidad'
    )
    iva_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='IVA (%)'
    )
    
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Subtotal'
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Total'
    )
    
    # Control de inventario
    afecto_inventario = models.BooleanField(
        default=True,
        verbose_name='Afectó inventario',
        help_text='False si viene de remisión convertida a factura'
    )
    
    class Meta:
        db_table = 'detalles_venta'
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'
        indexes = [
            models.Index(fields=['venta']),
            models.Index(fields=['producto']),
        ]


class AuditoriaDescuento(BaseModel):
    """Registro de todos los descuentos aplicados"""
    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name='auditorias_descuento',
        verbose_name='Venta'
    )
    vendedor = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='descuentos_aplicados',
        verbose_name='Vendedor'
    )
    descuento_solicitado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Descuento solicitado (%)'
    )
    descuento_permitido = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Descuento permitido (%)'
    )
    requirio_aprobacion = models.BooleanField(
        default=False,
        verbose_name='Requirió aprobación'
    )
    aprobado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='aprobaciones_descuento',
        verbose_name='Aprobado por'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    
    class Meta:
        db_table = 'auditoria_descuentos'
        verbose_name = 'Auditoría de Descuento'
        verbose_name_plural = 'Auditorías de Descuentos'
        ordering = ['-created_at']


class VentaAnulada(BaseModel):
    """Registro de ventas anuladas con su motivo"""
    venta = models.OneToOneField(
        Venta,
        on_delete=models.CASCADE,
        related_name='anulacion',
        verbose_name='Venta anulada'
    )
    
    MOTIVO_CHOICES = [
        ('DEVOLUCION_PARCIAL', 'Devolución Parcial'),
        ('DEVOLUCION_TOTAL', 'Devolución Total'),
        ('ERROR_PRECIOS', 'Error con Precios en la Remisión'),
        ('ERROR_CONCEPTO', 'Error por Concepto en la Remisión'),
        ('COMPRADOR_NO_ACEPTA', 'El Comprador no Acepta los Artículos'),
        ('OTRO', 'Otro'),
    ]
    
    motivo = models.CharField(
        max_length=50,
        choices=MOTIVO_CHOICES,
        verbose_name='Motivo de anulación'
    )
    descripcion = models.TextField(
        verbose_name='Descripción detallada'
    )
    anulado_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='ventas_anuladas',
        verbose_name='Anulado por'
    )
    devuelve_inventario = models.BooleanField(
        default=True,
        verbose_name='Devuelve al inventario',
        help_text='Si la mercancía regresa al stock'
    )
    
    class Meta:
        db_table = 'ventas_anuladas'
        verbose_name = 'Venta Anulada'
        verbose_name_plural = 'Ventas Anuladas'
