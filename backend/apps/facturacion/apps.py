from django.apps import AppConfig


class FacturacionConfig(AppConfig):
    """Configuración de la app de facturación electrónica."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.facturacion'
    verbose_name = 'Facturación electrónica'
