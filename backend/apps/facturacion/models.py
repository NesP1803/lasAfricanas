"""Modelos de facturación electrónica integrados con Factus."""

from django.db import models


class FacturaElectronica(models.Model):
    """Representa la respuesta validada de DIAN para una venta enviada a Factus."""

    STATUS_CHOICES = [
        ('ACEPTADA', 'Aceptada DIAN'),
        ('RECHAZADA', 'Rechazada DIAN'),
        ('ERROR', 'Error de envío'),
        ('EN_PROCESO', 'En proceso'),
    ]

    venta = models.OneToOneField(
        'ventas.Venta',
        on_delete=models.PROTECT,
        related_name='factura_electronica_factus',
        verbose_name='Venta',
    )
    cufe = models.CharField(max_length=128, unique=True, null=True, blank=True, db_index=True, verbose_name='CUFE')
    uuid = models.CharField(max_length=128, null=True, blank=True, db_index=True, verbose_name='UUID')
    number = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name='Número de factura')
    reference_code = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Código de referencia',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True, verbose_name='Estado DIAN')
    xml_url = models.URLField(max_length=500, null=True, blank=True, verbose_name='URL XML')
    pdf_url = models.URLField(max_length=500, null=True, blank=True, verbose_name='URL PDF')
    xml_local_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Ruta local XML')
    pdf_local_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Ruta local PDF')
    qr = models.ImageField(upload_to='facturas/qr/', null=True, blank=True, verbose_name='Código QR DIAN')
    codigo_error = models.CharField(max_length=50, null=True, blank=True, verbose_name='Código de error DIAN')
    mensaje_error = models.TextField(null=True, blank=True, verbose_name='Mensaje de error DIAN')
    response_json = models.JSONField(verbose_name='Respuesta completa de Factus')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

    class Meta:
        db_table = 'facturacion_facturas_electronicas'
        verbose_name = 'Factura Electrónica'
        verbose_name_plural = 'Facturas Electrónicas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['number', '-created_at']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self) -> str:
        return f'{self.number} - {self.cufe}'


class NotaCreditoElectronica(models.Model):
    """Representa una nota crédito electrónica emitida en Factus para una factura existente."""

    factura = models.ForeignKey(
        FacturaElectronica,
        on_delete=models.PROTECT,
        related_name='notas_credito',
    )
    number = models.CharField(max_length=50)
    uuid = models.CharField(max_length=100, null=True, blank=True)
    cufe = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=FacturaElectronica.STATUS_CHOICES, db_index=True)
    xml_url = models.URLField(null=True, blank=True)
    pdf_url = models.URLField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facturacion_notas_credito_electronicas'
        verbose_name = 'Nota Crédito Electrónica'
        verbose_name_plural = 'Notas Crédito Electrónicas'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.number} ({self.status})'


class DocumentoSoporteElectronico(models.Model):
    """Representa un documento soporte electrónico emitido para compras a no obligados."""

    number = models.CharField(max_length=50)
    proveedor_nombre = models.CharField(max_length=200)
    proveedor_documento = models.CharField(max_length=50)
    proveedor_tipo_documento = models.CharField(max_length=20)
    cufe = models.CharField(max_length=150, null=True, blank=True)
    uuid = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=FacturaElectronica.STATUS_CHOICES, db_index=True)
    xml_url = models.URLField(null=True, blank=True)
    pdf_url = models.URLField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facturacion_documentos_soporte_electronicos'
        verbose_name = 'Documento Soporte Electrónico'
        verbose_name_plural = 'Documentos Soporte Electrónicos'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.number} ({self.status})'


class NotaAjusteDocumentoSoporte(models.Model):
    """Representa una nota de ajuste emitida para un documento soporte electrónico."""

    documento_soporte = models.ForeignKey(
        DocumentoSoporteElectronico,
        on_delete=models.PROTECT,
        related_name='notas_ajuste',
    )
    number = models.CharField(max_length=50)
    uuid = models.CharField(max_length=100, null=True, blank=True)
    cufe = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=FacturaElectronica.STATUS_CHOICES, db_index=True)
    xml_url = models.URLField(null=True, blank=True)
    pdf_url = models.URLField(null=True, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facturacion_notas_ajuste_documento_soporte'
        verbose_name = 'Nota Ajuste Documento Soporte'
        verbose_name_plural = 'Notas Ajuste Documento Soporte'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.number} ({self.status})'


class RangoNumeracionDIAN(models.Model):
    """Rangos de numeración autorizados por DIAN sincronizados desde Factus."""

    ENVIRONMENT_CHOICES = [
        ('SANDBOX', 'Sandbox'),
        ('PRODUCTION', 'Producción'),
    ]
    DOCUMENT_CODE_CHOICES = [
        ('FACTURA_VENTA', 'Factura de venta'),
    ]

    factus_range_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='ID de rango en Factus',
    )
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default='SANDBOX',
        db_index=True,
        verbose_name='Entorno',
    )
    document_code = models.CharField(
        max_length=30,
        choices=DOCUMENT_CODE_CHOICES,
        default='FACTURA_VENTA',
        db_index=True,
        verbose_name='Tipo de documento',
    )
    is_active_remote = models.BooleanField(default=True, db_index=True, verbose_name='Activo remoto en Factus')
    is_selected_local = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Seleccionado localmente para facturar',
    )
    prefijo = models.CharField(max_length=20)
    desde = models.IntegerField()
    hasta = models.IntegerField()
    resolucion = models.CharField(max_length=100)
    consecutivo_actual = models.IntegerField()
    fecha_autorizacion = models.DateField(null=True)
    fecha_expiracion = models.DateField(null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facturacion_rangos_numeracion_dian'
        verbose_name = 'Rango de Numeración DIAN'
        verbose_name_plural = 'Rangos de Numeración DIAN'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['environment', 'document_code', 'is_active_remote']),
            models.Index(fields=['environment', 'document_code', 'is_selected_local']),
        ]

    def __str__(self) -> str:
        return f'{self.prefijo}: {self.desde}-{self.hasta}'


class ConfiguracionDIAN(models.Model):
    """Configuración DIAN editable desde el sistema."""

    nit_empresa = models.CharField(max_length=20)
    software_id = models.CharField(max_length=200)
    software_pin = models.CharField(max_length=200)
    prefijo_facturacion = models.CharField(max_length=20)
    rango_facturacion = models.ForeignKey(RangoNumeracionDIAN, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facturacion_configuracion_dian'
        verbose_name = 'Configuración DIAN'
        verbose_name_plural = 'Configuración DIAN'

    def __str__(self) -> str:
        return f'Configuración DIAN {self.nit_empresa}'
