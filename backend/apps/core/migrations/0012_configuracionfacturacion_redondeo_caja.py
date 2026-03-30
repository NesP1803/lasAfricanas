from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_fix_producto_iva_tribute'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionfacturacion',
            name='redondeo_caja_efectivo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='configuracionfacturacion',
            name='redondeo_caja_incremento',
            field=models.PositiveIntegerField(default=100),
        ),
    ]
