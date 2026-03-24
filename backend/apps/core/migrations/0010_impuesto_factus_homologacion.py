from django.db import migrations, models


def forwards(apps, schema_editor):
    Impuesto = apps.get_model('core', 'Impuesto')
    defaults = {
        'iva 19%': {'porcentaje': 19, 'factus_tribute_id': 18},
        'iva 0%': {'porcentaje': 0, 'factus_tribute_id': 21},
        'exento': {'porcentaje': 0, 'factus_tribute_id': 21},
    }
    for impuesto in Impuesto.objects.all():
        key = (impuesto.nombre or '').strip().lower()
        item = defaults.get(key)
        if not item:
            continue
        changed = False
        if impuesto.porcentaje != item['porcentaje']:
            impuesto.porcentaje = item['porcentaje']
            changed = True
        if not impuesto.factus_tribute_id:
            impuesto.factus_tribute_id = item['factus_tribute_id']
            changed = True
        if changed:
            impuesto.save(update_fields=['porcentaje', 'factus_tribute_id', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_merge_20260123_2158'),
    ]

    operations = [
        migrations.AddField(
            model_name='impuesto',
            name='factus_tribute_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='impuesto',
            name='porcentaje',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
