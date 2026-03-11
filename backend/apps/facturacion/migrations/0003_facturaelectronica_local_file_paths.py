from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0002_unify_factura_electronica'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturaelectronica',
            name='pdf_local_path',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='Ruta local PDF'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='xml_local_path',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='Ruta local XML'),
        ),
    ]
