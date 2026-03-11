from django.db import migrations, models
from django.utils import timezone


def _extract_response_value(payload, *keys):
    if not isinstance(payload, dict):
        return ''
    data = payload.get('data', payload)
    bill = data.get('bill', data) if isinstance(data, dict) else {}
    for key in keys:
        value = bill.get(key) if isinstance(bill, dict) else None
        if value:
            return str(value)
        value = data.get(key) if isinstance(data, dict) else None
        if value:
            return str(value)
        value = payload.get(key)
        if value:
            return str(value)
    return ''


def migrate_legacy_facturas(apps, schema_editor):
    LegacyFactura = apps.get_model('facturacion_electronica', 'FacturaElectronica')
    Factura = apps.get_model('facturacion', 'FacturaElectronica')

    for legacy in LegacyFactura.objects.all().iterator():
        response_json = legacy.respuesta_api or {}
        cufe = (legacy.cufe or _extract_response_value(response_json, 'cufe')).strip()
        if not cufe:
            continue

        if Factura.objects.filter(venta_id=legacy.venta_id).exists() or Factura.objects.filter(cufe=cufe).exists():
            continue

        uuid = (legacy.uuid_factus or _extract_response_value(response_json, 'uuid')).strip()
        number = (_extract_response_value(response_json, 'number') or legacy.reference_code or '').strip()
        xml_url = _extract_response_value(response_json, 'xml_url')
        pdf_url = _extract_response_value(response_json, 'pdf_url')
        qr = _extract_response_value(response_json, 'qr')
        status = (_extract_response_value(response_json, 'status') or legacy.estado or 'UNKNOWN').strip()

        if not all([uuid, number, xml_url, pdf_url, qr]):
            continue

        Factura.objects.create(
            venta_id=legacy.venta_id,
            cufe=cufe,
            uuid=uuid,
            number=number,
            status=status,
            xml_url=xml_url,
            pdf_url=pdf_url,
            qr=qr,
            response_json=response_json,
            created_at=legacy.created_at,
            updated_at=legacy.updated_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0001_initial'),
        ('facturacion_electronica', '0002_catalogos_factus'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturaelectronica',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=timezone.now, verbose_name='Fecha de actualización'),
            preserve_default=False,
        ),
        migrations.RunPython(migrate_legacy_facturas, migrations.RunPython.noop),
    ]
