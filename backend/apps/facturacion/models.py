"""Modelos de facturación electrónica integrados con Factus."""

from django.db import models


class FacturaElectronica(models.Model):
    """Representa la respuesta validada de DIAN para una venta enviada a Factus."""

    venta = models.OneToOneField(
        'ventas.Venta',
        on_delete=models.PROTECT,
        related_name='factura_electronica_factus',
        verbose_name='Venta',
    )
    cufe = models.CharField(max_length=128, unique=True, db_index=True, verbose_name='CUFE')
    uuid = models.CharField(max_length=128, db_index=True, verbose_name='UUID')
    number = models.CharField(max_length=64, db_index=True, verbose_name='Número de factura')
    status = models.CharField(max_length=64, db_index=True, verbose_name='Estado Factus/DIAN')
    xml_url = models.URLField(max_length=500, verbose_name='URL XML')
    pdf_url = models.URLField(max_length=500, verbose_name='URL PDF')
    xml_local_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Ruta local XML')
    pdf_local_path = models.CharField(max_length=500, blank=True, default='', verbose_name='Ruta local PDF')
    qr = models.TextField(verbose_name='Código QR')
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
