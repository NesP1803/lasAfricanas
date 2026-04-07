from django.core.management.base import BaseCommand, CommandError

from apps.facturacion.services.sync_numbering_ranges import sync_numbering_ranges


class Command(BaseCommand):
    help = 'Sincroniza rangos oficiales DIAN desde Factus.'

    def handle(self, *args, **options):
        try:
            synced = sync_numbering_ranges()
        except Exception as exc:  # pragma: no cover
            raise CommandError(f'No fue posible sincronizar rangos: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Rangos sincronizados: {len(synced)}'))
        for rango in synced:
            self.stdout.write(
                f'- doc={rango.document} prefix={rango.prefix} '
                f'resolution={rango.resolution_number} active={rango.is_active}'
            )
