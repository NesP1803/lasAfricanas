from django.db import migrations


def _extract_dict(value):
    return value if isinstance(value, dict) else {}


def migrate_legacy_domain_models(apps, schema_editor):
    LegacyNotaCredito = apps.get_model('facturacion_electronica', 'NotaCreditoElectronica')
    LegacyDocumentoSoporte = apps.get_model('facturacion_electronica', 'DocumentoSoporteElectronico')

    NotaCreditoCanonica = apps.get_model('facturacion', 'NotaCreditoElectronica')
    DocumentoSoporteCanonico = apps.get_model('facturacion', 'DocumentoSoporteElectronico')

    for legacy in LegacyNotaCredito.objects.all().iterator():
        response_json = _extract_dict(legacy.respuesta_api) or _extract_dict(legacy.payload)
        defaults = {
            'status': legacy.estado or 'EN_PROCESO',
            'response_json': response_json,
            'created_at': legacy.created_at,
        }
        NotaCreditoCanonica.objects.get_or_create(
            factura_id=legacy.factura_id,
            number=legacy.reference_code,
            defaults=defaults,
        )

    for legacy in LegacyDocumentoSoporte.objects.all().iterator():
        payload = _extract_dict(legacy.payload)
        response_json = _extract_dict(legacy.respuesta_api) or payload
        proveedor_nombre = (
            payload.get('proveedor_nombre')
            or payload.get('customer', {}).get('company')
            or payload.get('customer', {}).get('names')
            or 'Proveedor migrado'
        )
        proveedor_tipo_documento = (
            payload.get('proveedor_tipo_documento')
            or payload.get('customer', {}).get('identification_document_id')
            or '13'
        )
        defaults = {
            'proveedor_nombre': str(proveedor_nombre)[:200],
            'proveedor_documento': legacy.tercero_identificacion,
            'proveedor_tipo_documento': str(proveedor_tipo_documento)[:20],
            'status': legacy.estado or 'EN_PROCESO',
            'response_json': response_json,
            'created_at': legacy.created_at,
        }
        DocumentoSoporteCanonico.objects.get_or_create(
            number=legacy.reference_code,
            defaults=defaults,
        )


def noop_reverse(apps, schema_editor):
    """Migración irreversible: evita recrear modelos legacy eliminados."""


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0006_documentosoporteelectronico'),
        ('facturacion_electronica', '0006_alter_documentoidentificacionfactus_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_domain_models, noop_reverse),
        migrations.DeleteModel(
            name='NotaCreditoElectronica',
        ),
        migrations.DeleteModel(
            name='DocumentoSoporteElectronico',
        ),
    ]
