from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.facturacion_electronica.catalogos.models import (  # noqa: F401
    DocumentoIdentificacionFactus,
    MetodoPagoFactus,
    MunicipioFactus,
    TributoFactus,
    UnidadMedidaFactus,
)


class FacturaElectronica(BaseModel):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ENVIANDO = 'ENVIANDO', 'Enviando'
        ACEPTADA_DIAN = 'ACEPTADA_DIAN', 'Aceptada por DIAN'
        RECHAZADA_DIAN = 'RECHAZADA_DIAN', 'Rechazada por DIAN'
        ERROR_API = 'ERROR_API', 'Error API'

    venta = models.OneToOneField(
        'ventas.Venta',
        on_delete=models.PROTECT,
        related_name='factura_electronica',
        verbose_name='Venta',
    )
    reference_code = models.CharField(
        max_length=80,
        unique=True,
        db_index=True,
        verbose_name='Reference code',
    )
    numbering_range_id = models.PositiveIntegerField(verbose_name='Rango de numeración Factus')
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
        verbose_name='Estado',
    )
    payload = models.JSONField(default=dict, blank=True, verbose_name='Payload enviado')
    respuesta_api = models.JSONField(default=dict, blank=True, verbose_name='Respuesta Factus')
    uuid_factus = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='UUID Factus')
    cufe = models.CharField(max_length=100, blank=True, db_index=True, verbose_name='CUFE')
    intentos_envio = models.PositiveSmallIntegerField(default=0, verbose_name='Intentos de envío')
    ultimo_intento_at = models.DateTimeField(null=True, blank=True, verbose_name='Último intento')
    enviada_at = models.DateTimeField(null=True, blank=True, verbose_name='Enviada a Factus')
    aceptada_at = models.DateTimeField(null=True, blank=True, verbose_name='Aceptada por DIAN')

    class Meta:
        db_table = 'facturas_electronicas'
        verbose_name = 'Factura Electrónica'
        verbose_name_plural = 'Facturas Electrónicas'
        indexes = [
            models.Index(fields=['estado', 'created_at']),
            models.Index(fields=['ultimo_intento_at']),
        ]

    def marcar_intento(self):
        self.intentos_envio += 1
        self.ultimo_intento_at = timezone.now()

    def __str__(self):
        return f'{self.reference_code} ({self.estado})'


class NotaCreditoElectronica(BaseModel):
    factura = models.ForeignKey(
        FacturaElectronica,
        on_delete=models.PROTECT,
        related_name='notas_credito',
        verbose_name='Factura electrónica',
    )
    reference_code = models.CharField(max_length=80, unique=True, db_index=True)
    estado = models.CharField(max_length=20, default=FacturaElectronica.Estado.PENDIENTE)
    payload = models.JSONField(default=dict, blank=True)
    respuesta_api = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'notas_credito_electronicas'
        verbose_name = 'Nota Crédito Electrónica'
        verbose_name_plural = 'Notas Crédito Electrónicas'


class DocumentoSoporteElectronico(BaseModel):
    reference_code = models.CharField(max_length=80, unique=True, db_index=True)
    tercero_identificacion = models.CharField(max_length=50)
    estado = models.CharField(max_length=20, default=FacturaElectronica.Estado.PENDIENTE)
    payload = models.JSONField(default=dict, blank=True)
    respuesta_api = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'documentos_soporte_electronicos'
        verbose_name = 'Documento Soporte Electrónico'
        verbose_name_plural = 'Documentos Soporte Electrónicos'


class FactusToken(models.Model):
    access_token = models.TextField(verbose_name='Access token')
    token_type = models.CharField(max_length=40, default='Bearer', verbose_name='Token type')
    expires_in = models.PositiveIntegerField(default=0, verbose_name='Duración en segundos')
    expires_at = models.DateTimeField(db_index=True, verbose_name='Expira en')
    scope = models.CharField(max_length=255, blank=True, verbose_name='Scope')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'factus_tokens'
        verbose_name = 'Token Factus'
        verbose_name_plural = 'Tokens Factus'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.token_type} - {self.expires_at.isoformat()}'


class HomologacionMunicipio(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    municipality_id = models.PositiveIntegerField(db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_municipio'
        verbose_name = 'Homologación Municipio'
        verbose_name_plural = 'Homologaciones Municipio'


class HomologacionTributo(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    tribute_id = models.PositiveIntegerField(db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_tributo'
        verbose_name = 'Homologación Tributo'
        verbose_name_plural = 'Homologaciones Tributo'


class HomologacionUnidadMedida(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    unit_measure_id = models.PositiveIntegerField(db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_unidad_medida'
        verbose_name = 'Homologación Unidad de Medida'
        verbose_name_plural = 'Homologaciones Unidad de Medida'


class HomologacionMedioPago(BaseModel):
    codigo_interno = models.CharField(max_length=100, unique=True, db_index=True)
    payment_method_code = models.CharField(max_length=20, db_index=True)
    nombre = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = 'fe_homologacion_medio_pago'
        verbose_name = 'Homologación Medio de Pago'
        verbose_name_plural = 'Homologaciones Medio de Pago'
