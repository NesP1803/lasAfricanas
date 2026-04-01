from apps.taller.models import Moto
from apps.intercambio_datos.services.mappers.relation_resolver import resolve_cliente_by_documento


def import_row(data):
    placa = str(data.get('placa', '')).strip().upper()
    if not placa:
        return 'ERROR', None, 'placa requerida'
    cliente = resolve_cliente_by_documento(data.get('cliente_documento'))
    obj, created = Moto.objects.update_or_create(
        placa=placa,
        defaults={
            'marca': str(data.get('marca', '')).strip(),
            'modelo': str(data.get('modelo', '')).strip(),
            'color': str(data.get('color', '')).strip(),
            'cliente': cliente,
        }
    )
    return ('INSERTADA' if created else 'ACTUALIZADA'), obj, ''
