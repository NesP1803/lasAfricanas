from django.apps import AppConfig


class FacturacionElectronicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.facturacion_electronica'
    verbose_name = 'Facturación Electrónica'

    def ready(self):
        import apps.facturacion_electronica.signals  # noqa: F401
