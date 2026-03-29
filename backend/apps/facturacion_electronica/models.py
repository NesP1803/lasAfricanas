from django.db import models

from apps.core.models import BaseModel
from apps.facturacion_electronica.catalogos.models import (  # noqa: F401
    DocumentoIdentificacionFactus,
    MetodoPagoFactus,
    MunicipioFactus,
    TributoFactus,
    UnidadMedidaFactus,
)


# Esta app solo contiene infraestructura/integración con Factus.
# El dominio de documentos electrónicos vive en apps.facturacion.
class FactusToken(models.Model):
    access_token = models.TextField(verbose_name='Access token')
    refresh_token = models.TextField(blank=True, default='', verbose_name='Refresh token')
    token_type = models.CharField(max_length=40, default='Bearer', verbose_name='Token type')
    expires_in = models.PositiveIntegerField(default=0, verbose_name='Duración en segundos')
    refresh_expires_in = models.PositiveIntegerField(default=0, verbose_name='Refresh duración en segundos')
    expires_at = models.DateTimeField(db_index=True, verbose_name='Expira en')
    refresh_expires_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='Refresh expira en')
    scope = models.CharField(max_length=255, blank=True, verbose_name='Scope')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'factus_tokens'
        verbose_name = 'Token Factus'
        verbose_name_plural = 'Tokens Factus'
        ordering = ['-created_at']


class HomologacionMunicipio(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    municipality_id = models.PositiveIntegerField(db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_municipio'


class HomologacionTributo(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    tribute_id = models.PositiveIntegerField(db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_tributo'


class HomologacionUnidadMedida(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    unit_measure_id = models.PositiveIntegerField(db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_unidad_medida'


class HomologacionMedioPago(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    payment_method_code = models.CharField(max_length=20, db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_medio_pago'
