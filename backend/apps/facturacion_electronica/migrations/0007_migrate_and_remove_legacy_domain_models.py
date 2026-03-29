from django.db import migrations


STATUS_MAP = {
    'PENDIENTE': 'EN_PROCESO',
    'ENVIANDO': 'EN_PROCESO',
    'ACEPTADA_DIAN': 'ACEPTADA',
    'RECHAZADA_DIAN': 'RECHAZADA',
    'ERROR_API': 'ERROR',
}


def _extract_dict(value):
    return value if isinstance(value, dict) else {}


def _normalize_status(legacy_status):
    if not legacy_status:
        return 'EN_PROCESO'
    return STATUS_MAP.get(str(legacy_status).strip().upper(), 'EN_PROCESO')


def _pick_first(source, *keys):
    for key in keys:
        value = source.get(key)
        if value not in (None, ''):
            return value
    return None


def _prefer_non_empty(current, incoming):
    return current if current not in (None, '') else incoming


def migrate_legacy_domain_models(apps, schema_editor):
    LegacyNotaCredito = apps.get_model('facturacion_electronica', 'NotaCreditoElectronica')
    LegacyDocumentoSoporte = apps.get_model('facturacion_electronica', 'DocumentoSoporteElectronico')

    NotaCreditoCanonica = apps.get_model('facturacion', 'NotaCreditoElectronica')
    DocumentoSoporteCanonico = apps.get_model('facturacion', 'DocumentoSoporteElectronico')

    for legacy in LegacyNotaCredito.objects.all().iterator():
        payload = _extract_dict(legacy.payload)
        respuesta_api = _extract_dict(legacy.respuesta_api)
        response_json = respuesta_api or payload

        canonical, _ = NotaCreditoCanonica.objects.update_or_create(
            factura_id=legacy.factura_id,
            number=legacy.reference_code,
            defaults={
                'status': _normalize_status(legacy.estado),
                'response_json': response_json,
                'created_at': legacy.created_at,
            },
        )

        canonical.cufe = _prefer_non_empty(
            canonical.cufe,
            _pick_first(respuesta_api, 'cufe', 'bill_cufe') or _pick_first(payload, 'cufe', 'bill_cufe'),
        )
        canonical.uuid = _prefer_non_empty(
            canonical.uuid,
            _pick_first(respuesta_api, 'uuid', 'bill_uuid') or _pick_first(payload, 'uuid', 'bill_uuid'),
        )
        canonical.xml_url = _prefer_non_empty(
            canonical.xml_url,
            _pick_first(respuesta_api, 'xml_url', 'url_xml') or _pick_first(payload, 'xml_url', 'url_xml'),
        )
        canonical.pdf_url = _prefer_non_empty(
            canonical.pdf_url,
            _pick_first(respuesta_api, 'pdf_url', 'url_pdf') or _pick_first(payload, 'pdf_url', 'url_pdf'),
        )
        canonical.save(update_fields=['cufe', 'uuid', 'xml_url', 'pdf_url'])

    for legacy in LegacyDocumentoSoporte.objects.all().iterator():
        payload = _extract_dict(legacy.payload)
        respuesta_api = _extract_dict(legacy.respuesta_api)
        response_json = respuesta_api or payload

        # Defaults defensivos: el modelo legacy no almacenaba todos los atributos
        # estructurados que hoy requiere el modelo canónico.
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

        canonical, _ = DocumentoSoporteCanonico.objects.update_or_create(
            number=legacy.reference_code,
            defaults={
                'proveedor_nombre': str(proveedor_nombre)[:200],
                'proveedor_documento': legacy.tercero_identificacion,
                'proveedor_tipo_documento': str(proveedor_tipo_documento)[:20],
                'status': _normalize_status(legacy.estado),
                'response_json': response_json,
                'created_at': legacy.created_at,
            },
        )

        canonical.cufe = _prefer_non_empty(
            canonical.cufe,
            _pick_first(respuesta_api, 'cufe', 'bill_cufe') or _pick_first(payload, 'cufe', 'bill_cufe'),
        )
        canonical.uuid = _prefer_non_empty(
            canonical.uuid,
            _pick_first(respuesta_api, 'uuid', 'bill_uuid') or _pick_first(payload, 'uuid', 'bill_uuid'),
        )
        canonical.xml_url = _prefer_non_empty(
            canonical.xml_url,
            _pick_first(respuesta_api, 'xml_url', 'url_xml') or _pick_first(payload, 'xml_url', 'url_xml'),
        )
        canonical.pdf_url = _prefer_non_empty(
            canonical.pdf_url,
            _pick_first(respuesta_api, 'pdf_url', 'url_pdf') or _pick_first(payload, 'pdf_url', 'url_pdf'),
        )
        canonical.save(update_fields=['cufe', 'uuid', 'xml_url', 'pdf_url'])


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
