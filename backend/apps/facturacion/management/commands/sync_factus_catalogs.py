from django.core.management.base import BaseCommand, CommandError

from apps.facturacion.services.catalog_sync_service import CatalogSyncService
from apps.facturacion.services.factus_client import FactusAPIError


class Command(BaseCommand):
    help = 'Sincroniza catálogos de referencia desde Factus a tablas locales.'

    def handle(self, *args, **options):
        service = CatalogSyncService()
        jobs = [
            ('municipios', service.sync_municipalities),
            ('tributos', service.sync_tributes),
            ('métodos de pago', service.sync_payment_methods),
            ('unidades de medida', service.sync_unit_measures),
            ('documentos de identificación', service.sync_identification_documents),
        ]
        for label, fn in jobs:
            try:
                result = fn()
            except FactusAPIError as exc:
                raise CommandError(f'No se pudo sincronizar {label}: {exc}') from exc
            self.stdout.write(
                self.style.SUCCESS(
                    f'{label}: fetched={result["fetched"]}, created={result["created"]}, '
                    f'updated={result["updated"]}, deactivated={result["deactivated"]}'
                )
            )
