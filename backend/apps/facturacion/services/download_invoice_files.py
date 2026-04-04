"""Descarga y persistencia local de XML/PDF de facturas electrónicas."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from django.conf import settings

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient

logger = logging.getLogger(__name__)


def decode_base64_to_bytes(encoded_content: str, *, document_type: str) -> bytes:
    encoded = str(encoded_content or '').strip()
    if not encoded:
        raise DescargaFacturaError(f'Factus no devolvió contenido base64 para {document_type}.')
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise DescargaFacturaError(f'Contenido base64 inválido para {document_type}.') from exc


def persist_file_bytes(*, folder: str, filename: str, content: bytes) -> str:
    safe_name = Path(str(filename or '').strip()).name or 'documento'
    relative_path = (Path('facturas') / folder / safe_name).as_posix()
    full_path = Path(settings.MEDIA_ROOT) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    return relative_path


def _extract_filename(payload: dict, *, fallback: str) -> str:
    data = payload.get('data', payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return fallback
    name = str(data.get('file_name') or data.get('filename') or fallback).strip()
    return Path(name).name or fallback


def _download_invoice_file(factura: FacturaElectronica, folder: str, extension: str, field: str) -> str:
    if not factura.number:
        raise DescargaFacturaError('La factura no tiene número electrónico para descargar archivos.')

    client = FactusClient()
    try:
        if extension == 'xml':
            payload = client.get_invoice_xml_payload(factura.number)
            data = payload.get('data', payload) if isinstance(payload, dict) else {}
            filename = _extract_filename(payload, fallback=f'{factura.number}.xml')
            encoded = str(data.get('xml_base_64_encoded', '')).strip() if isinstance(data, dict) else ''
            content = decode_base64_to_bytes(encoded, document_type='XML')
            endpoint = client.invoice_download_xml_path.format(number=factura.number)
        else:
            payload = client.get_invoice_pdf_payload(factura.number)
            data = payload.get('data', payload) if isinstance(payload, dict) else {}
            filename = _extract_filename(payload, fallback=f'{factura.number}.pdf')
            encoded = str(data.get('pdf_base_64_encoded', '')).strip() if isinstance(data, dict) else ''
            content = decode_base64_to_bytes(encoded, document_type='PDF')
            endpoint = client.invoice_download_pdf_path.format(number=factura.number)

        relative_path = persist_file_bytes(folder=folder, filename=filename, content=content)
        setattr(factura, field, relative_path)
        factura.save(update_fields=[field, 'updated_at'])
        logger.info('factura_descarga.ok number=%s endpoint=%s', factura.number, endpoint)
        return relative_path
    except FactusAPIError as exc:
        logger.warning('factura_descarga.error number=%s endpoint=factus_api', factura.number, exc_info=True)
        raise DescargaFacturaError(
            f'No fue posible descargar el archivo {extension.upper()} de la factura {factura.number}.'
        ) from exc
    except DescargaFacturaError:
        logger.warning('factura_descarga.error number=%s endpoint=factus_base64', factura.number, exc_info=True)
        raise


def download_xml(factura: FacturaElectronica) -> str:
    """Descarga y almacena localmente el XML de la factura."""
    return _download_invoice_file(
        factura=factura,
        folder='xml',
        extension='xml',
        field='xml_local_path',
    )


def download_pdf(factura: FacturaElectronica) -> str:
    """Descarga y almacena localmente el PDF de la factura."""
    return _download_invoice_file(
        factura=factura,
        folder='pdf',
        extension='pdf',
        field='pdf_local_path',
    )
