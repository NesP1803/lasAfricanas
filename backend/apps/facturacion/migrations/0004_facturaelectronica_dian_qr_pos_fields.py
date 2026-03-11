from django.db import migrations, models


def populate_reference_and_status(apps, schema_editor):
    FacturaElectronica = apps.get_model('facturacion', 'FacturaElectronica')
    status_mapping = {
        'valid': 'ACEPTADA',
        'aceptada_dian': 'ACEPTADA',
        'validada': 'ACEPTADA',
        'rejected': 'RECHAZADA',
        'rechazada_dian': 'RECHAZADA',
        'pending': 'EN_PROCESO',
        'pendiente': 'EN_PROCESO',
        'en_proceso': 'EN_PROCESO',
        'error': 'ERROR',
    }

    for factura in FacturaElectronica.objects.all().iterator():
        if not factura.reference_code:
            factura.reference_code = factura.number

        normalized = (factura.status or '').strip().lower()
        factura.status = status_mapping.get(normalized, 'ERROR')

        factura.save(update_fields=['reference_code', 'status', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0003_facturaelectronica_local_file_paths'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturaelectronica',
            name='codigo_error',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Código de error DIAN'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='mensaje_error',
            field=models.TextField(blank=True, null=True, verbose_name='Mensaje de error DIAN'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='reference_code',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Código de referencia'),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='qr',
            field=models.ImageField(blank=True, null=True, upload_to='facturas/qr/', verbose_name='Código QR DIAN'),
        ),
        migrations.RunPython(populate_reference_and_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='reference_code',
            field=models.CharField(max_length=100, unique=True, verbose_name='Código de referencia'),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='status',
            field=models.CharField(
                choices=[
                    ('ACEPTADA', 'Aceptada DIAN'),
                    ('RECHAZADA', 'Rechazada DIAN'),
                    ('ERROR', 'Error de envío'),
                    ('EN_PROCESO', 'En proceso'),
                ],
                db_index=True,
                max_length=20,
                verbose_name='Estado DIAN',
            ),
        ),
    ]
