from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import BaseModel
from decimal import Decimal


class Categoria(BaseModel):
    """Categorías de productos de Las Africanas"""
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nombre'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    orden = models.IntegerField(
        default=0,
        verbose_name='Orden',
        help_text='Para ordenar las categorías en el sistema'
    )
    
    class Meta:
        db_table = 'categorias'
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['orden', 'nombre']
        indexes = [
            models.Index(fields=['nombre']),
        ]
    
    def __str__(self):
        return self.nombre


class Proveedor(BaseModel):
    """Proveedores de repuestos"""
    nombre = models.CharField(
        max_length=200,
        unique=True,
        verbose_name='Nombre'
    )
    nit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='NIT'
    )
    telefono = models.CharField(
        max_length=20,
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
    contacto = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Persona de contacto'
    )
    
    class Meta:
        db_table = 'proveedores'
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['nit']),
        ]
    
    def __str__(self):
        return self.nombre


class Producto(BaseModel):
    """Productos/Repuestos del inventario"""
    codigo = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='Código',
        help_text='Código de barras o SKU'
    )
    nombre = models.CharField(
        max_length=300,
        db_index=True,
        verbose_name='Nombre del producto'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    
    # Relaciones
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name='Categoría'
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name='Proveedor',
        null=True,
        blank=True,
    )
    
    # Precios
    precio_costo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio de costo'
    )
    precio_venta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        db_index=True,
        verbose_name='Precio de venta'
    )
    precio_venta_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Precio de venta mínimo',
        help_text='Precio mínimo permitido (con descuento máximo)'
    )
    
    # Inventario
    stock = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name='Stock actual'
    )
    stock_minimo = models.IntegerField(
        default=5,
        verbose_name='Stock mínimo',
        help_text='Alerta cuando el stock llegue a este nivel'
    )
    unidad_medida = models.CharField(
        max_length=20,
        default='UND',
        verbose_name='Unidad de medida',
        help_text='UND, PAR, KG, LT, etc.'
    )
    
    # IVA
    iva_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=19,
        verbose_name='IVA (%)'
    )
    
    # Flags
    aplica_descuento = models.BooleanField(
        default=True,
        verbose_name='Aplica descuento'
    )
    es_servicio = models.BooleanField(
        default=False,
        verbose_name='Es servicio',
        help_text='Marca si es un servicio en lugar de producto físico'
    )
    
    class Meta:
        db_table = 'productos'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['nombre']),
            models.Index(fields=['categoria', 'is_active']),
            models.Index(fields=['stock']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @property
    def stock_bajo(self):
        """Verifica si el stock está bajo"""
        return self.stock <= self.stock_minimo
    
    @property
    def margen_utilidad(self):
        """Calcula el margen de utilidad"""
        if self.precio_costo > 0:
            return ((self.precio_venta - self.precio_costo) / self.precio_costo) * 100
        return 0
    
    @property
    def valor_inventario(self):
        """Valor total del inventario de este producto"""
        return self.precio_costo * self.stock


class MovimientoInventario(BaseModel):
    """Historial de movimientos de inventario"""
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada (Compra)'),
        ('SALIDA', 'Salida (Venta)'),
        ('AJUSTE', 'Ajuste Manual'),
        ('DEVOLUCION', 'Devolución'),
        ('BAJA', 'Dar de Baja'),
    ]
    
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='movimientos',
        verbose_name='Producto'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_MOVIMIENTO,
        db_index=True,
        verbose_name='Tipo de movimiento'
    )
    cantidad = models.IntegerField(
        verbose_name='Cantidad',
        help_text='Positivo para entradas, negativo para salidas'
    )
    stock_anterior = models.IntegerField(
        verbose_name='Stock anterior'
    )
    stock_nuevo = models.IntegerField(
        verbose_name='Stock nuevo'
    )
    
    costo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Costo unitario'
    )
    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        verbose_name='Usuario'
    )
    
    referencia = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Referencia',
        help_text='No. Factura, Remisión, etc.'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    
    class Meta:
        db_table = 'movimientos_inventario'
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['producto', 'created_at']),
            models.Index(fields=['tipo', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.codigo} ({self.cantidad})"
