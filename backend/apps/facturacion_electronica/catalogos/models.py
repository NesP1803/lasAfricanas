from django.db import models

from apps.core.models import BaseModel


class CatalogoFactusBase(BaseModel):
    factus_id = models.PositiveIntegerField(unique=True, db_index=True)
    codigo = models.CharField(max_length=50, db_index=True)
    nombre = models.CharField(max_length=255)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['factus_id']),
            models.Index(fields=['codigo']),
        ]

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'


class MunicipioFactus(CatalogoFactusBase):
    class Meta(CatalogoFactusBase.Meta):
        db_table = 'fe_catalogo_municipio'
        verbose_name = 'Municipio Factus'
        verbose_name_plural = 'Municipios Factus'


class TributoFactus(CatalogoFactusBase):
    class Meta(CatalogoFactusBase.Meta):
        db_table = 'fe_catalogo_tributo'
        verbose_name = 'Tributo Factus'
        verbose_name_plural = 'Tributos Factus'


class MetodoPagoFactus(CatalogoFactusBase):
    class Meta(CatalogoFactusBase.Meta):
        db_table = 'fe_catalogo_metodo_pago'
        verbose_name = 'Método de Pago Factus'
        verbose_name_plural = 'Métodos de Pago Factus'


class UnidadMedidaFactus(CatalogoFactusBase):
    class Meta(CatalogoFactusBase.Meta):
        db_table = 'fe_catalogo_unidad_medida'
        verbose_name = 'Unidad de Medida Factus'
        verbose_name_plural = 'Unidades de Medida Factus'


class DocumentoIdentificacionFactus(CatalogoFactusBase):
    class Meta(CatalogoFactusBase.Meta):
        db_table = 'fe_catalogo_documento_identificacion'
        verbose_name = 'Documento de Identificación Factus'
        verbose_name_plural = 'Documentos de Identificación Factus'
