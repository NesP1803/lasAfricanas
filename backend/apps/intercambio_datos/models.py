from django.conf import settings
from django.db import models
from apps.core.models import BaseModel


class ImportProfile(BaseModel):
    PRECIO_SOURCE = [
        ('FINAL', 'Precio final'),
        ('BASE_SIN_IVA', 'Precio base sin IVA'),
    ]

    nombre = models.CharField(max_length=120, unique=True)
    codigo = models.SlugField(max_length=120, unique=True)
    precio_fuente = models.CharField(max_length=20, choices=PRECIO_SOURCE, default='FINAL')
    activo = models.BooleanField(default=True)
    configuracion = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'intercambio_import_profile'
        ordering = ['nombre']


class ImportJob(BaseModel):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('ANALIZADO', 'Analizado'),
        ('EJECUTADO', 'Ejecutado'),
        ('ERROR', 'Error'),
    ]

    perfil = models.ForeignKey(ImportProfile, on_delete=models.PROTECT, related_name='jobs')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='intercambio_import_jobs')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    dry_run_hash = models.CharField(max_length=64, blank=True)
    resumen = models.JSONField(default=dict, blank=True)
    errores = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'intercambio_import_job'
        ordering = ['-created_at']


class ImportFile(BaseModel):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name='files')
    nombre = models.CharField(max_length=255)
    archivo = models.FileField(upload_to='intercambio/imports/')
    extension = models.CharField(max_length=10)
    checksum = models.CharField(max_length=64, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'intercambio_import_file'


class ImportSheetAnalysis(BaseModel):
    file = models.ForeignKey(ImportFile, on_delete=models.CASCADE, related_name='sheets')
    sheet_name = models.CharField(max_length=255)
    entidad_detectada = models.CharField(max_length=64, blank=True)
    confianza = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    mapping = models.JSONField(default=dict, blank=True)
    resumen = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'intercambio_import_sheet_analysis'


class ImportRowResult(BaseModel):
    ACCIONES = [
        ('INSERTADA', 'Insertada'),
        ('ACTUALIZADA', 'Actualizada'),
        ('OMITIDA', 'Omitida'),
        ('AMBIGUA', 'Ambigua'),
        ('ERROR', 'Error'),
        ('WARNING', 'Warning'),
    ]

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name='row_results')
    file = models.ForeignKey(ImportFile, on_delete=models.CASCADE, related_name='row_results')
    sheet = models.ForeignKey(ImportSheetAnalysis, on_delete=models.CASCADE, related_name='row_results')
    row_number = models.PositiveIntegerField()
    action = models.CharField(max_length=20, choices=ACCIONES)
    natural_key = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'intercambio_import_row_result'
        indexes = [models.Index(fields=['job', 'action'])]


class ExportProfile(BaseModel):
    nombre = models.CharField(max_length=120, unique=True)
    codigo = models.SlugField(max_length=120, unique=True)
    entidades = models.JSONField(default=list, blank=True)
    multihoja = models.BooleanField(default=True)

    class Meta:
        db_table = 'intercambio_export_profile'


class ExportJob(BaseModel):
    ESTADOS = [('PENDIENTE', 'Pendiente'), ('GENERADO', 'Generado'), ('ERROR', 'Error')]

    perfil = models.ForeignKey(ExportProfile, on_delete=models.PROTECT, related_name='jobs')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='intercambio_export_jobs')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    archivo = models.FileField(upload_to='intercambio/exports/', blank=True, null=True)
    resumen = models.JSONField(default=dict, blank=True)
    errores = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'intercambio_export_job'
        ordering = ['-created_at']
