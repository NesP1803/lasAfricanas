from django.core.management.base import BaseCommand, CommandError

from apps.facturacion.services.sync_numbering_ranges import sync_factus_dian_ranges


class Command(BaseCommand):
    help = 'Sincroniza rangos DIAN autorizados desde Factus (/v1/numbering-ranges/dian).'

    def handle(self, *args, **options):
        try:
            synced = sync_factus_dian_ranges()
        except Exception as exc:  # pragma: no cover
            raise CommandError(f'No fue posible sincronizar rangos DIAN desde Factus: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Rangos sincronizados: {len(synced)}'))
