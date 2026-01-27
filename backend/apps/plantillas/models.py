from django.conf import settings
from django.db import models


class DocumentType(models.TextChoices):
    QUOTATION = 'QUOTATION', 'Cotización'
    INVOICE = 'INVOICE', 'Factura de venta'
    DELIVERY_NOTE = 'DELIVERY_NOTE', 'Remisión'
    CREDIT_NOTE = 'CREDIT_NOTE', 'Nota crédito'
    DEBIT_NOTE = 'DEBIT_NOTE', 'Nota débito'


class OutputType(models.TextChoices):
    PDF = 'PDF', 'PDF'
    RECEIPT = 'RECEIPT', 'Tirilla'


class Template(models.Model):
    name = models.CharField(max_length=150)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    output_type = models.CharField(max_length=20, choices=OutputType.choices)
    is_active = models.BooleanField(default=False, db_index=True)
    current_version = models.ForeignKey(
        'TemplateVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_templates'
        verbose_name = 'Plantilla de documento'
        verbose_name_plural = 'Plantillas de documentos'
        indexes = [
            models.Index(fields=['document_type', 'output_type', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.document_type} - {self.output_type})"


class TemplateVersion(models.Model):
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    version_number = models.PositiveIntegerField()
    html = models.TextField(blank=True, null=True)
    css = models.TextField(blank=True, null=True)
    receipt_text = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='template_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    comment = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'document_template_versions'
        verbose_name = 'Versión de plantilla'
        verbose_name_plural = 'Versiones de plantillas'
        ordering = ['-version_number']
        unique_together = ('template', 'version_number')

    def __str__(self):
        return f"{self.template.name} v{self.version_number}"
