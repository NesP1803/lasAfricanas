from django.db import migrations


def forwards(apps, schema_editor):
    Impuesto = apps.get_model('core', 'Impuesto')
    objetivos = {'iva 19%', 'iva19', 'iva 19'}

    for impuesto in Impuesto.objects.all():
        nombre = (impuesto.nombre or '').strip().lower()
        if nombre in objetivos or impuesto.porcentaje == 19:
            if impuesto.factus_tribute_id != 1:
                impuesto.factus_tribute_id = 1
                impuesto.save(update_fields=['factus_tribute_id', 'updated_at'])


def backwards(apps, schema_editor):
    """No-op: no se restaura id anterior porque era homologación incorrecta."""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_impuesto_factus_homologacion'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
