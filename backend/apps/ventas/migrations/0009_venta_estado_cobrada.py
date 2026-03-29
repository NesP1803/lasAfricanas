from django.db import migrations, models


def forwards_migrate_facturada_to_cobrada(apps, schema_editor):
    Venta = apps.get_model('ventas', 'Venta')
    Venta.objects.filter(estado='FACTURADA').update(estado='COBRADA')


def backwards_migrate_cobrada_to_facturada(apps, schema_editor):
    # No-op seguro: no revertir masivamente COBRADA -> FACTURADA porque
    # mezclaría ventas que originalmente eran no-facturables o creadas
    # después de aplicar la migración.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0008_venta_inventario_ya_afectado'),
    ]

    operations = [
        migrations.RunPython(
            forwards_migrate_facturada_to_cobrada,
            backwards_migrate_cobrada_to_facturada,
        ),
        migrations.AlterField(
            model_name='venta',
            name='estado',
            field=models.CharField(
                choices=[
                    ('BORRADOR', 'Borrador'),
                    ('ENVIADA_A_CAJA', 'Enviada a caja'),
                    ('COBRADA', 'Cobrada'),
                    ('FACTURADA', 'Facturada (legacy)'),
                    ('ANULADA', 'Anulada'),
                ],
                db_index=True,
                default='BORRADOR',
                max_length=20,
                verbose_name='Estado',
            ),
        ),
    ]
