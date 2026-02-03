from django.db import migrations, models
import decimal


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='stock',
            field=models.DecimalField(
                db_index=True,
                decimal_places=2,
                default=decimal.Decimal('0.00'),
                max_digits=12,
                verbose_name='Stock actual',
            ),
        ),
        migrations.AlterField(
            model_name='producto',
            name='stock_minimo',
            field=models.DecimalField(
                decimal_places=2,
                default=decimal.Decimal('5.00'),
                help_text='Alerta cuando el stock llegue a este nivel',
                max_digits=12,
                verbose_name='Stock mínimo',
            ),
        ),
        migrations.AlterField(
            model_name='movimientoinventario',
            name='cantidad',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Positivo para entradas, negativo para salidas',
                max_digits=12,
                verbose_name='Cantidad',
            ),
        ),
        migrations.AlterField(
            model_name='movimientoinventario',
            name='stock_anterior',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                verbose_name='Stock anterior',
            ),
        ),
        migrations.AlterField(
            model_name='movimientoinventario',
            name='stock_nuevo',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                verbose_name='Stock nuevo',
            ),
        ),
    ]
