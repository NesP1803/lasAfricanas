from django.core.management.base import BaseCommand, CommandError

from apps.facturacion.services.catalog_sync_service import CatalogSyncService
from apps.facturacion.services.factus_client import FactusAPIError


class Command(BaseCommand):
    help = 'Sincroniza catálogos de referencia desde Factus a tablas locales.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-remote',
            action='store_true',
            help='Omite llamadas al API de Factus y solo asegura semillas mínimas locales.',
        )
        parser.add_argument(
            '--ensure-minimums',
            action='store_true',
            help='Después de sincronizar, garantiza catálogos mínimos para homologaciones críticas.',
        )

    def handle(self, *args, **options):
        service = CatalogSyncService()
        skip_remote = bool(options.get('skip_remote'))
        ensure_minimums = bool(options.get('ensure_minimums')) or skip_remote

        jobs = [
            ('municipios', service.sync_municipalities),
            ('tributos', service.sync_tributes),
            ('métodos de pago', service.sync_payment_methods),
            ('unidades de medida', service.sync_unit_measures),
            ('documentos de identificación', service.sync_identification_documents),
        ]
        if not skip_remote:
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
        if ensure_minimums:
            result = service.ensure_minimum_catalogs()
            self.stdout.write(
                self.style.SUCCESS(
                    'semillas mínimas: '
                    f'documentos={result["documentos_identificacion"]}, '
                    f'municipios={result["municipios"]}, '
                    f'tributos={result["tributos"]}, '
                    f'unidades={result["unidades_medida"]}, '
                    f'metodos_pago={result["metodos_pago"]}'
                )
            )
