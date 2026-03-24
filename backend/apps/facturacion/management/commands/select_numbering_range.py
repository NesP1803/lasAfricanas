from django.core.management.base import BaseCommand, CommandError

from apps.facturacion.models import RangoNumeracionDIAN


class Command(BaseCommand):
    help = 'Selecciona localmente el rango de numeración para un entorno/documento.'

    def add_arguments(self, parser):
        parser.add_argument('--factus-id', type=int, required=True, help='ID del rango en Factus')
        parser.add_argument('--environment', type=str, default='SANDBOX', choices=['SANDBOX', 'PRODUCTION'])
        parser.add_argument('--document-code', type=str, default='FACTURA_VENTA')

    def handle(self, *args, **options):
        factus_id = options['factus_id']
        environment = options['environment']
        document_code = options['document_code']

        rango = RangoNumeracionDIAN.objects.filter(
            factus_range_id=factus_id,
            environment=environment,
            document_code=document_code,
        ).first()
        if rango is None:
            raise CommandError(
                f'No existe rango local factus_id={factus_id} environment={environment} document_code={document_code}. '
                'Debe sincronizar primero.'
            )

        RangoNumeracionDIAN.objects.filter(environment=environment, document_code=document_code).update(
            is_selected_local=False
        )
        rango.is_selected_local = True
        rango.save(update_fields=['is_selected_local'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Rango seleccionado: env={environment} doc={document_code} factus_id={rango.factus_range_id} prefijo={rango.prefijo}'
            )
        )
