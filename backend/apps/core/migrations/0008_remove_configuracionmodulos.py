from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_configuracionfacturacion_plantilla_factura_carta_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ConfiguracionModulos',
        ),
    ]
