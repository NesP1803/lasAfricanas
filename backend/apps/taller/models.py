from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import BaseModel
from apps.inventario.models import Producto, Proveedor
from apps.ventas.models import Cliente, Venta


class Mecanico(BaseModel):
    """Mecánicos registrados en el taller."""
    nombre = models.CharField(max_length=200, unique=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    ciudad = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'mecanicos'
        verbose_name = 'Mecánico'
        verbose_name_plural = 'Mecánicos'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
        ]

    def __str__(self):
        return self.nombre


class Moto(BaseModel):
    """Motos registradas en el taller."""
    placa = models.CharField(max_length=20, unique=True)
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=50, blank=True)
    anio = models.IntegerField(null=True, blank=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='motos',
        null=True,
        blank=True
    )
    mecanico = models.ForeignKey(
        Mecanico,
        on_delete=models.PROTECT,
        related_name='motos',
        null=True,
        blank=True
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='motos',
        null=True,
        blank=True
    )
    fecha_ingreso = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        db_table = 'motos'
        verbose_name = 'Moto'
        verbose_name_plural = 'Motos'
        ordering = ['placa']
        indexes = [
            models.Index(fields=['placa']),
            models.Index(fields=['marca']),
        ]

    def __str__(self):
        return f"{self.placa} - {self.marca}"


class OrdenTaller(BaseModel):
    """Orden de trabajo del taller."""
    ESTADOS = [
        ('EN_PROCESO', 'En proceso'),
        ('LISTO_FACTURAR', 'Listo para facturar'),
        ('FACTURADO', 'Facturado'),
    ]

    moto = models.ForeignKey(
        Moto,
        on_delete=models.PROTECT,
        related_name='ordenes'
    )
    mecanico = models.ForeignKey(
        Mecanico,
        on_delete=models.PROTECT,
        related_name='ordenes'
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default='EN_PROCESO')
    observaciones = models.TextField(blank=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    venta = models.ForeignKey(
        Venta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes_taller'
    )

    class Meta:
        db_table = 'ordenes_taller'
        verbose_name = 'Orden de taller'
        verbose_name_plural = 'Órdenes de taller'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"Orden {self.id} - {self.moto.placa}"

    @property
    def total_repuestos(self):
        return sum((repuesto.subtotal for repuesto in self.repuestos.all()), Decimal('0'))


class OrdenRepuesto(BaseModel):
    """Repuestos asociados a una orden."""
    orden = models.ForeignKey(
        OrdenTaller,
        on_delete=models.CASCADE,
        related_name='repuestos'
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='repuestos_taller'
    )
    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'ordenes_repuestos'
        verbose_name = 'Repuesto de orden'
        verbose_name_plural = 'Repuestos de orden'
        ordering = ['-created_at']
        unique_together = ('orden', 'producto')

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * Decimal(self.precio_unitario)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.nombre} ({self.cantidad})"
