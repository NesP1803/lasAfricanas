from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0007_merge_20260202_2033'),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='inventario_ya_afectado',
            field=models.BooleanField(
                default=False,
                help_text='Indica si el inventario ya fue descontado por un flujo externo (p. ej. taller).',
                verbose_name='Inventario ya afectado',
            ),
        ),
    ]
