"""Modelos de facturación electrónica integrados con Factus."""

from django.db import models


class FacturaElectronica(models.Model):
    """Representa la respuesta validada de DIAN para una venta enviada a Factus."""

    ELECTRONIC_STATUS_CHOICES = [
        ('ACEPTADA', 'Aceptada'),
        ('ACEPTADA_CON_OBSERVACIONES', 'Aceptada con observaciones'),
        ('RECHAZADA', 'Rechazada'),
        ('ERROR_INTEGRACION', 'Error de integración'),
        ('ERROR_PERSISTENCIA', 'Error de persistencia'),
        ('PENDIENTE_REINTENTO', 'Pendiente de reintento'),
    ]
    CREDIT_STATUS_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('CREDITADA_PARCIAL', 'Creditada parcial'),
        ('CREDITADA_TOTAL', 'Creditada total'),
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
    status = models.CharField(
        max_length=40,
        choices=ELECTRONIC_STATUS_CHOICES,
        db_index=True,
        verbose_name='Estado electrónico (legacy)',
        default='PENDIENTE_REINTENTO',
    )
    estado_electronico = models.CharField(
        max_length=40,
        choices=ELECTRONIC_STATUS_CHOICES,
        db_index=True,
        verbose_name='Estado electrónico Factus',
        default='PENDIENTE_REINTENTO',
    )
    estado_factus_raw = models.CharField(max_length=120, blank=True, default='', verbose_name='Estado crudo Factus')
    xml_url = models.URLField(max_length=2048, null=True, blank=True, verbose_name='URL XML')
    pdf_url = models.URLField(max_length=2048, null=True, blank=True, verbose_name='URL PDF')
    public_url = models.URLField(max_length=2048, null=True, blank=True, verbose_name='URL pública')
    qr_data = models.TextField(null=True, blank=True, verbose_name='Contenido QR')
    qr_image_url = models.URLField(max_length=2048, null=True, blank=True, verbose_name='URL imagen QR remota')
    qr_image_data = models.TextField(null=True, blank=True, verbose_name='Contenido QR embebido/base64')
    xml_local_path = models.TextField(blank=True, default='', verbose_name='Ruta local XML')
    pdf_local_path = models.TextField(blank=True, default='', verbose_name='Ruta local PDF')
    qr = models.ImageField(upload_to='facturas/qr/', null=True, blank=True, verbose_name='Código QR DIAN')
    pdf_uploaded_to_factus = models.BooleanField(default=False, verbose_name='PDF personalizado cargado en Factus')
    pdf_uploaded_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha carga PDF en Factus')
    correo_enviado = models.BooleanField(default=False, verbose_name='Correo enviado por Factus')
    correo_enviado_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha envío de correo')
    ultimo_error_correo = models.TextField(null=True, blank=True, verbose_name='Último error de correo')
    ultimo_error_pdf = models.TextField(null=True, blank=True, verbose_name='Último error PDF')
    codigo_error = models.CharField(max_length=50, null=True, blank=True, verbose_name='Código de error DIAN')
    mensaje_error = models.TextField(null=True, blank=True, verbose_name='Mensaje de error DIAN')
    observaciones_json = models.JSONField(default=list, blank=True, verbose_name='Observaciones Factus normalizadas')
    response_json = models.JSONField(verbose_name='Respuesta completa de Factus')
    retry_count = models.PositiveIntegerField(default=0, verbose_name='Cantidad de reintentos')
    last_retry_at = models.DateTimeField(null=True, blank=True, verbose_name='Último reintento')
    next_retry_at = models.DateTimeField(null=True, blank=True, verbose_name='Próximo reintento')
    ultima_sincronizacion_at = models.DateTimeField(null=True, blank=True, verbose_name='Última sincronización')
    emitida_en_factus = models.BooleanField(default=False, db_index=True, verbose_name='Emitida en Factus')
    estado_acreditacion = models.CharField(
        max_length=30,
        choices=CREDIT_STATUS_CHOICES,
        default='ACTIVA',
        db_index=True,
        verbose_name='Estado comercial de acreditación',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

    class Meta:
        db_table = 'facturacion_facturas_electronicas'
        verbose_name = 'Factura Electrónica'
        verbose_name_plural = 'Facturas Electrónicas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['estado_electronico', '-created_at']),
            models.Index(fields=['number', '-created_at']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self) -> str:
        return f'{self.number} - {self.cufe}'


class NotaCreditoElectronica(models.Model):
    """Representa una nota crédito electrónica emitida en Factus para una factura existente."""
    NOTE_TYPE_CHOICES = [
        ('PARCIAL', 'Parcial'),
        ('TOTAL', 'Total'),
    ]
    LOCAL_STATUS_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE_ENVIO', 'Pendiente de envío'),
        ('EN_PROCESO', 'En proceso DIAN'),
        ('ACEPTADA', 'Aceptada'),
        ('RECHAZADA', 'Rechazada'),
        ('ERROR_INTEGRACION', 'Error de integración'),
        ('ERROR_PERSISTENCIA', 'Error de persistencia'),
        ('ANULADA_LOCAL', 'Anulada local'),
        ('ELIMINADA_EN_FACTUS', 'Eliminada en Factus'),
    ]

    factura = models.ForeignKey(
        FacturaElectronica,
        on_delete=models.PROTECT,
        related_name='notas_credito',
    )
    venta_origen = models.ForeignKey(
        'ventas.Venta',
        on_delete=models.PROTECT,
        related_name='notas_credito_electronicas',
        null=True,
        blank=True,
    )
    number = models.CharField(max_length=50, db_index=True)
    prefijo = models.CharField(max_length=20, blank=True, default='')
    consecutivo = models.CharField(max_length=30, blank=True, default='')
    reference_code = models.CharField(max_length=120, blank=True, default='', db_index=True)
    tipo_nota = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='PARCIAL', db_index=True)
    concepto = models.CharField(max_length=120, blank=True, default='')
    motivo = models.TextField(blank=True, default='')
    estado_local = models.CharField(max_length=40, choices=LOCAL_STATUS_CHOICES, default='BORRADOR', db_index=True)
    estado_electronico = models.CharField(
        max_length=40,
        choices=FacturaElectronica.ELECTRONIC_STATUS_CHOICES,
        default='PENDIENTE_REINTENTO',
        db_index=True,
    )
    status_raw_factus = models.CharField(max_length=120, blank=True, default='')
    uuid = models.CharField(max_length=100, null=True, blank=True)
    cufe = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(
        max_length=40,
        choices=FacturaElectronica.ELECTRONIC_STATUS_CHOICES,
        db_index=True,
        default='PENDIENTE_REINTENTO',
    )
    xml_url = models.URLField(null=True, blank=True)
    pdf_url = models.URLField(null=True, blank=True)
    public_url = models.URLField(max_length=2048, null=True, blank=True)
    qr = models.TextField(blank=True, default='')
    qr_image_url = models.URLField(max_length=2048, null=True, blank=True)
    pdf_local_path = models.TextField(blank=True, default='')
    xml_local_path = models.TextField(blank=True, default='')
    correo_enviado = models.BooleanField(default=False)
    correo_enviado_at = models.DateTimeField(null=True, blank=True)
    email_content_json = models.JSONField(default=dict, blank=True)
    email_status = models.CharField(max_length=40, blank=True, default='')
    codigo_error = models.CharField(max_length=50, null=True, blank=True)
    mensaje_error = models.TextField(null=True, blank=True)
    request_json = models.JSONField(default=dict, blank=True)
    response_json = models.JSONField(null=True, blank=True)
    synchronized_at = models.DateTimeField(null=True, blank=True)
    remote_status_raw = models.CharField(max_length=200, blank=True, default='')
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'facturacion_notas_credito_electronicas'
        verbose_name = 'Nota Crédito Electrónica'
        verbose_name_plural = 'Notas Crédito Electrónicas'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['factura', 'tipo_nota'],
                condition=models.Q(
                    estado_local__in=['BORRADOR', 'PENDIENTE_ENVIO', 'EN_PROCESO', 'ACEPTADA']
                ),
                name='uq_nota_credito_abierta_factura_tipo',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.number} ({self.status})'


class NotaCreditoDetalle(models.Model):
    """Detalle por línea acreditada para control de parciales/saldos."""

    nota_credito = models.ForeignKey(
        NotaCreditoElectronica,
        on_delete=models.CASCADE,
        related_name='detalles',
    )
    detalle_venta_original = models.ForeignKey(
        'ventas.DetalleVenta',
        on_delete=models.PROTECT,
        related_name='notas_credito_detalle',
    )
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT)
    cantidad_original_facturada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cantidad_ya_acreditada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cantidad_a_acreditar = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    base_impuesto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    impuesto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    afecta_inventario = models.BooleanField(default=False)
    motivo_linea = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'facturacion_notas_credito_detalle'
        verbose_name = 'Detalle de nota crédito'
        verbose_name_plural = 'Detalles de nota crédito'
        indexes = [
            models.Index(fields=['detalle_venta_original']),
            models.Index(fields=['producto']),
        ]


class DocumentoSoporteElectronico(models.Model):
    """Representa un documento soporte electrónico emitido para compras a no obligados."""

    number = models.CharField(max_length=50)
    proveedor_nombre = models.CharField(max_length=200)
    proveedor_documento = models.CharField(max_length=50)
    proveedor_tipo_documento = models.CharField(max_length=20)
    cufe = models.CharField(max_length=150, null=True, blank=True)
    uuid = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=40, choices=FacturaElectronica.ELECTRONIC_STATUS_CHOICES, db_index=True)
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
    status = models.CharField(max_length=40, choices=FacturaElectronica.ELECTRONIC_STATUS_CHOICES, db_index=True)
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
