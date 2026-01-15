from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_add_plantillas_facturacion"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="configuracionfacturacion",
            name="plantilla_factura_carta",
        ),
        migrations.RemoveField(
            model_name="configuracionfacturacion",
            name="plantilla_factura_tirilla",
        ),
        migrations.RemoveField(
            model_name="configuracionfacturacion",
            name="plantilla_remision_carta",
        ),
        migrations.RemoveField(
            model_name="configuracionfacturacion",
            name="plantilla_remision_tirilla",
        ),
        migrations.RemoveField(
            model_name="configuracionfacturacion",
            name="plantilla_nota_credito_carta",
        ),
        migrations.RemoveField(
            model_name="configuracionfacturacion",
            name="plantilla_nota_credito_tirilla",
        ),
    ]
