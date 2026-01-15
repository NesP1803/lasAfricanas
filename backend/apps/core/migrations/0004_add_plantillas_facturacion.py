from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_create_configuracion_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracionfacturacion",
            name="plantilla_factura_carta",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="configuracionfacturacion",
            name="plantilla_factura_tirilla",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="configuracionfacturacion",
            name="plantilla_remision_carta",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="configuracionfacturacion",
            name="plantilla_remision_tirilla",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="configuracionfacturacion",
            name="plantilla_nota_credito_carta",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="configuracionfacturacion",
            name="plantilla_nota_credito_tirilla",
            field=models.TextField(blank=True),
        ),
    ]
