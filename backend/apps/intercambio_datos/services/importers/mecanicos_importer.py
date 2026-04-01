from apps.taller.models import Mecanico


def import_row(data):
    nombre = str(data.get('nombre', '')).strip()
    if not nombre:
        return 'ERROR', None, 'nombre requerido'
    if str(data.get('tipo_usuario', '')).strip().lower() in {'empleado', 'vendedor', 'cajero'}:
        return 'AMBIGUA', None, 'fila corresponde a empleado, no mecánico'
    obj, created = Mecanico.objects.update_or_create(
        nombre=nombre,
        defaults={
            'telefono': str(data.get('telefono', '')).strip(),
            'email': str(data.get('email', '')).strip(),
            'direccion': str(data.get('direccion', '')).strip(),
            'ciudad': str(data.get('ciudad', '')).strip(),
        }
    )
    return ('INSERTADA' if created else 'ACTUALIZADA'), obj, ''
