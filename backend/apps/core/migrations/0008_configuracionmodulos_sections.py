from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_configuracionfacturacion_plantilla_factura_carta_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionmodulos',
            name='facturacion_cuentas_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='configuracionmodulos',
            name='facturacion_listado_facturas_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='configuracionmodulos',
            name='facturacion_venta_rapida_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='configuracionmodulos',
            name='taller_operaciones_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='configuracionmodulos',
            name='taller_registro_motos_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
