from django.core.management.base import BaseCommand

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services import FacturaNoEncontrada, FactusConsultaError, sync_invoice_status


class Command(BaseCommand):
    help = 'Sincroniza estado DIAN de facturas pendientes contra Factus.'

    def handle(self, *args, **options):
        pendientes = FacturaElectronica.objects.filter(status__in=['EN_PROCESO', 'PENDIENTE']).values_list(
            'number',
            flat=True,
        )
        total = 0
        ok = 0
        failed = 0

        for number in pendientes:
            total += 1
            try:
                factura = sync_invoice_status(number)
                ok += 1
                self.stdout.write(self.style.SUCCESS(f'{number}: {factura.status}'))
            except (FacturaNoEncontrada, FactusConsultaError) as exc:
                failed += 1
                self.stderr.write(self.style.WARNING(f'{number}: {exc}'))

        self.stdout.write(f'Sincronización finalizada. total={total} ok={ok} failed={failed}')
