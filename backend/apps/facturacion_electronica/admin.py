from django.contrib import admin

from .models import (
    FacturaElectronica,
    NotaCreditoElectronica,
    DocumentoSoporteElectronico,
    FactusToken,
    HomologacionMunicipio,
    HomologacionTributo,
    HomologacionUnidadMedida,
    HomologacionMedioPago,
)


@admin.register(FacturaElectronica)
class FacturaElectronicaAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'venta', 'estado', 'intentos_envio', 'ultimo_intento_at')
    list_filter = ('estado',)
    search_fields = ('reference_code', 'venta__numero_comprobante', 'uuid_factus', 'cufe')
    readonly_fields = ('payload', 'respuesta_api')


admin.site.register(NotaCreditoElectronica)
admin.site.register(DocumentoSoporteElectronico)
admin.site.register(FactusToken)
admin.site.register(HomologacionMunicipio)
admin.site.register(HomologacionTributo)
admin.site.register(HomologacionUnidadMedida)
admin.site.register(HomologacionMedioPago)
