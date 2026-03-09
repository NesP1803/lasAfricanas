from django.core.management.base import BaseCommand, CommandError

from apps.facturacion_electronica.services.catalog_service import (
    sync_identification_documents,
    sync_municipalities,
    sync_payment_methods,
    sync_tributes,
    sync_unit_measures,
)
from apps.facturacion_electronica.services.factus_client import FactusAPIError


class Command(BaseCommand):
    help = 'Sincroniza catálogos de referencia desde Factus a tablas locales.'

    def handle(self, *args, **options):
        jobs = [
            ('municipios', sync_municipalities),
            ('tributos', sync_tributes),
            ('métodos de pago', sync_payment_methods),
            ('unidades de medida', sync_unit_measures),
            ('documentos de identificación', sync_identification_documents),
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
