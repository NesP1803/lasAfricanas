from django.contrib import admin

from apps.facturacion.models import FacturaElectronica
from .models import (
    DocumentoSoporteElectronico,
    FactusToken,
    HomologacionMedioPago,
    HomologacionMunicipio,
    HomologacionTributo,
    HomologacionUnidadMedida,
    NotaCreditoElectronica,
)


@admin.register(FacturaElectronica)
class FacturaElectronicaAdmin(admin.ModelAdmin):
    list_display = ('number', 'venta', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('number', 'venta__numero_comprobante', 'uuid', 'cufe')
    readonly_fields = ('response_json',)


admin.site.register(NotaCreditoElectronica)
admin.site.register(DocumentoSoporteElectronico)
admin.site.register(FactusToken)
admin.site.register(HomologacionMunicipio)
admin.site.register(HomologacionTributo)
admin.site.register(HomologacionUnidadMedida)
admin.site.register(HomologacionMedioPago)
