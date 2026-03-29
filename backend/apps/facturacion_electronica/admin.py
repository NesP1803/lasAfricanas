from django.contrib import admin

from .models import (
    FactusToken,
    HomologacionMedioPago,
    HomologacionMunicipio,
    HomologacionTributo,
    HomologacionUnidadMedida,
)

# Esta app registra solo administración de integración Factus, no dominio de negocio.
admin.site.register(FactusToken)
admin.site.register(HomologacionMunicipio)
admin.site.register(HomologacionTributo)
admin.site.register(HomologacionUnidadMedida)
admin.site.register(HomologacionMedioPago)
