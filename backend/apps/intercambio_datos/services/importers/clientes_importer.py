from apps.ventas.models import Cliente


def import_row(data):
    natural_key = str(data.get('numero_documento', '')).strip()
    if not natural_key:
        return 'ERROR', None, 'numero_documento requerido'
    defaults = {
        'nombre': str(data.get('nombre', '')).strip(),
        'telefono': str(data.get('telefono', '')).strip(),
        'email': str(data.get('email', '')).strip(),
        'direccion': str(data.get('direccion', '')).strip(),
        'ciudad': str(data.get('ciudad', '')).strip(),
    }
    instance, created = Cliente.objects.update_or_create(numero_documento=natural_key, defaults=defaults)
    return ('INSERTADA' if created else 'ACTUALIZADA'), instance, ''
