from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0009_venta_estado_cobrada"),
    ]

    operations = [
        migrations.AlterField(
            model_name="venta",
            name="efectivo_recibido",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name="Efectivo recibido"),
        ),
        migrations.AlterField(
            model_name="venta",
            name="cambio",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name="Cambio"),
        ),
    ]
