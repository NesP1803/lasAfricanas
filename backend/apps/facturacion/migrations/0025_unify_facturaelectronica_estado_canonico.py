from django.db import migrations


DEFAULT_STATE = 'PENDIENTE_REINTENTO'


def forwards(apps, schema_editor):
    FacturaElectronica = apps.get_model('facturacion', 'FacturaElectronica')
    for factura in FacturaElectronica.objects.all().only('id', 'estado_electronico', 'status'):
        estado = (factura.estado_electronico or '').strip() or (factura.status or '').strip() or DEFAULT_STATE
        factura.estado_electronico = estado
        factura.status = estado
        factura.save(update_fields=['estado_electronico', 'status'])


def backwards(apps, schema_editor):
    FacturaElectronica = apps.get_model('facturacion', 'FacturaElectronica')
    for factura in FacturaElectronica.objects.all().only('id', 'estado_electronico', 'status'):
        estado = (factura.estado_electronico or '').strip() or DEFAULT_STATE
        factura.status = estado
        factura.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0024_facturaelectronica_assets_email_fields'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
