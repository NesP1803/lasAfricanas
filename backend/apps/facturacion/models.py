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
    cufe = models.CharField(max_length=128, unique=True, db_index=True, verbose_name='CUFE')
    uuid = models.CharField(max_length=128, db_index=True, verbose_name='UUID')
    number = models.CharField(max_length=64, db_index=True, verbose_name='Número de factura')
    reference_code = models.CharField(max_length=100, unique=True, verbose_name='Código de referencia')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True, verbose_name='Estado DIAN')
    xml_url = models.URLField(max_length=500, verbose_name='URL XML')
    pdf_url = models.URLField(max_length=500, verbose_name='URL PDF')
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
