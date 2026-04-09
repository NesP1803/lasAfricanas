"""Sincronización de activos documentales de facturas electrónicas."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.reconciliation import extract_factus_data

logger = logging.getLogger(__name__)


def decode_base64_file(encoded: str) -> bytes:
    encoded_value = str(encoded or '').strip()
    if not encoded_value:
        raise DescargaFacturaError('Factus no devolvió contenido base64 para el archivo solicitado.')
    try:
        return base64.b64decode(encoded_value, validate=True)
    except Exception as exc:
        raise DescargaFacturaError('Factus devolvió contenido base64 inválido.') from exc


def _extract_data(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get('data', payload)
    return data if isinstance(data, dict) else {}


def _store_bytes(*, folder: str, fallback_name: str, filename: str | None, content: bytes) -> str:
    safe_filename = Path(str(filename or '').strip()).name or fallback_name
    relative_path = (Path('facturas') / folder / safe_filename).as_posix()
    output = Path(settings.MEDIA_ROOT) / relative_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    return relative_path


def store_factura_pdf(factura: FacturaElectronica, payload: dict[str, Any]) -> str:
    data = _extract_data(payload)
    pdf_encoded = str(data.get('pdf_base_64_encoded') or '').strip()
    content = decode_base64_file(pdf_encoded)
    filename = str(data.get('file_name') or data.get('filename') or f'{factura.number}.pdf').strip()
    path = _store_bytes(folder='pdf', fallback_name=f'{factura.number}.pdf', filename=filename, content=content)
    factura.pdf_local_path = path
    return path


def store_factura_xml(factura: FacturaElectronica, payload: dict[str, Any]) -> str:
    data = _extract_data(payload)
    xml_encoded = str(data.get('xml_base_64_encoded') or '').strip()
    content = decode_base64_file(xml_encoded)
    filename = str(data.get('file_name') or data.get('filename') or f'{factura.number}.xml').strip()
    path = _store_bytes(folder='xml', fallback_name=f'{factura.number}.xml', filename=filename, content=content)
    factura.xml_local_path = path
    return path


def store_factura_email_zip(factura: FacturaElectronica, payload: dict[str, Any]) -> str:
    data = _extract_data(payload)
    zip_encoded = str(data.get('zip_base_64_encoded') or '').strip()
    content = decode_base64_file(zip_encoded)
    filename = str(data.get('file_name') or data.get('filename') or f'{factura.number}-email.zip').strip()
    path = _store_bytes(folder='correo', fallback_name=f'{factura.number}-email.zip', filename=filename, content=content)
    factura.email_zip_local_path = path
    factura.email_subject = str(data.get('subject') or factura.email_subject or '').strip()
    return path


def sync_invoice_assets(
    factura: FacturaElectronica,
    *,
    include_email_content: bool = False,
    force: bool = False,
    fallback_response_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not factura.number and factura.pk:
        factura.refresh_from_db()

    if not factura.number and isinstance(fallback_response_payload, dict):
        extracted = extract_factus_data(fallback_response_payload)
        number = str(extracted.get('number') or '').strip()
        if number:
            factura.number = number
            if not factura.reference_code and extracted.get('reference_code'):
                factura.reference_code = str(extracted.get('reference_code') or '').strip()
            factura.save(update_fields=['number', 'reference_code', 'updated_at'])

    if not factura.number:
        logger.warning(
            'factura_assets.sync_skip_missing_number factura_id=%s include_email_content=%s force=%s',
            factura.pk,
            include_email_content,
            force,
        )
        factura.last_assets_sync_at = timezone.now()
        factura.save(update_fields=['last_assets_sync_at', 'updated_at'])
        return {
            'pdf_local_path': factura.pdf_local_path,
            'xml_local_path': factura.xml_local_path,
            'email_zip_local_path': factura.email_zip_local_path,
            'email_subject': factura.email_subject,
            'include_email_content': include_email_content,
            'synced': {'pdf': False, 'xml': False, 'email_zip': False},
            'skipped': 'missing_number',
        }

    client = FactusClient()
    synced: dict[str, bool] = {'pdf': False, 'xml': False, 'email_zip': False}

    if force or not factura.pdf_local_path:
        pdf_payload = client.get_bill_pdf(factura.number)
        store_factura_pdf(factura, pdf_payload)
        synced['pdf'] = True

    if force or not factura.xml_local_path:
        xml_payload = client.get_bill_xml(factura.number)
        store_factura_xml(factura, xml_payload)
        synced['xml'] = True

    should_sync_email = include_email_content or (not factura.send_email_enabled)
    if should_sync_email and (force or not factura.email_zip_local_path):
        email_payload = client.get_bill_email_content(factura.number)
        data = _extract_data(email_payload)
        if data.get('zip_base_64_encoded'):
            store_factura_email_zip(factura, email_payload)
            synced['email_zip'] = True
        elif data.get('subject'):
            factura.email_subject = str(data.get('subject') or '').strip()

    factura.last_assets_sync_at = timezone.now()
    factura.save(
        update_fields=[
            'pdf_local_path',
            'xml_local_path',
            'email_zip_local_path',
            'email_subject',
            'last_assets_sync_at',
            'updated_at',
        ]
    )
    logger.info(
        'factura_assets.sync factura_id=%s number=%s force=%s include_email_content=%s synced=%s',
        factura.id,
        factura.number,
        force,
        include_email_content,
        synced,
    )
    return {
        'pdf_local_path': factura.pdf_local_path,
        'xml_local_path': factura.xml_local_path,
        'email_zip_local_path': factura.email_zip_local_path,
        'email_subject': factura.email_subject,
        'include_email_content': should_sync_email,
        'synced': synced,
    }
