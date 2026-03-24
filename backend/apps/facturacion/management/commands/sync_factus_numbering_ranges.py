from django.core.management.base import BaseCommand, CommandError

from apps.facturacion.services.sync_numbering_ranges import sync_numbering_ranges


class Command(BaseCommand):
    help = 'Sincroniza rangos de numeración de Factus al almacenamiento local.'

    def handle(self, *args, **options):
        try:
            synced = sync_numbering_ranges()
        except Exception as exc:  # pragma: no cover
            raise CommandError(f'No fue posible sincronizar rangos: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Rangos sincronizados: {len(synced)}'))
        for rango in synced:
            self.stdout.write(
                f'- env={rango.environment} doc={rango.document_code} factus_id={rango.factus_range_id} '
                f'prefijo={rango.prefijo} activo_remoto={rango.is_active_remote} seleccionado_local={rango.is_selected_local}'
            )
