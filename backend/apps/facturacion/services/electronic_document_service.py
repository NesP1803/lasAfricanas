"""Servicio unificado para descargas y correo de documentos electrónicos vía Factus."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from django.conf import settings

from apps.facturacion.services.download_resource_files import DownloadResourceError, read_local_media_file
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusValidationError

logger = logging.getLogger(__name__)

DocumentType = Literal['invoice', 'credit_note', 'support_document']
FileType = Literal['pdf', 'xml']


@dataclass(frozen=True)
class DownloadedDocument:
    content: bytes
    filename: str
    source: str
    local_path: str


class ElectronicDocumentFileService:
    """Orquesta descarga/lectura local y envío de correo para Factus."""

    _DOC_FOLDER = {
        'invoice': 'facturas',
        'credit_note': 'notas_credito',
        'support_document': 'documentos_soporte',
    }

    _DOWNLOAD_MAP: dict[tuple[DocumentType, FileType], tuple[str, str, str]] = {
        ('invoice', 'pdf'): ('bill_download_pdf_path', 'get_invoice_pdf_payload', 'pdf_base_64_encoded'),
        ('invoice', 'xml'): ('bill_download_xml_path', 'get_invoice_xml_payload', 'xml_base_64_encoded'),
        ('credit_note', 'pdf'): ('credit_note_download_pdf_path', 'get_credit_note_pdf_payload', 'pdf_base_64_encoded'),
        ('credit_note', 'xml'): ('credit_note_download_xml_path', 'get_credit_note_xml_payload', 'xml_base_64_encoded'),
        ('support_document', 'pdf'): (
            'support_document_download_pdf_path',
            'get_support_document_pdf_payload',
            'pdf_base_64_encoded',
        ),
        ('support_document', 'xml'): (
            'support_document_download_xml_path',
            'get_support_document_xml_payload',
            'xml_base_64_encoded',
        ),
    }

    def __init__(self, *, client: FactusClient | None = None) -> None:
        self.client = client or FactusClient()

    def download_invoice_pdf(self, number: str, *, factura=None, force_remote: bool = False) -> DownloadedDocument:
        return self.download_document_file('invoice', 'pdf', number, instance=factura, force_remote=force_remote)

    def download_invoice_xml(self, number: str, *, factura=None, force_remote: bool = False) -> DownloadedDocument:
        return self.download_document_file('invoice', 'xml', number, instance=factura, force_remote=force_remote)

    def download_credit_note_pdf(self, number: str, *, note=None, force_remote: bool = False) -> DownloadedDocument:
        return self.download_document_file('credit_note', 'pdf', number, instance=note, force_remote=force_remote)

    def download_credit_note_xml(self, number: str, *, note=None, force_remote: bool = False) -> DownloadedDocument:
        return self.download_document_file('credit_note', 'xml', number, instance=note, force_remote=force_remote)

    def download_support_document_pdf(self, number: str, *, support_document=None, force_remote: bool = False) -> DownloadedDocument:
        return self.download_document_file('support_document', 'pdf', number, instance=support_document, force_remote=force_remote)

    def download_support_document_xml(self, number: str, *, support_document=None, force_remote: bool = False) -> DownloadedDocument:
        return self.download_document_file('support_document', 'xml', number, instance=support_document, force_remote=force_remote)

    def send_invoice_email(self, number: str, email: str, pdf_base64: str | None = None) -> dict[str, Any]:
        return self.client.send_invoice_email(number, email=email, pdf_base_64_encoded=pdf_base64)

    def send_credit_note_email(self, number: str, email: str, pdf_base64: str | None = None) -> dict[str, Any]:
        return self.client.send_credit_note_email(number, email=email, pdf_base_64_encoded=pdf_base64)

    def get_invoice_email_content(self, number: str) -> dict[str, Any]:
        return self.client.get_invoice_email_content(number)

    def download_document_file(
        self,
        document_type: DocumentType,
        file_type: FileType,
        number: str,
        *,
        instance: Any | None = None,
        force_remote: bool = False,
    ) -> DownloadedDocument:
        if not str(number or '').strip():
            raise FactusValidationError('El documento electrónico no tiene number para descargar archivos.')

        local_path = ''
        local_filename = f'{number}.{file_type}'
        if instance is not None:
            local_path = str(getattr(instance, f'{file_type}_local_path', '') or '').strip()
            if local_path:
                local_filename = Path(local_path).name or local_filename
        if local_path and not force_remote:
            try:
                content = read_local_media_file(local_path)
                return DownloadedDocument(content=content, filename=local_filename, source='local', local_path=local_path)
            except DownloadResourceError:
                logger.warning(
                    'electronic_document.local_missing document_type=%s file_type=%s number=%s local_path=%s',
                    document_type,
                    file_type,
                    number,
                    local_path,
                )

        endpoint_attr, payload_method_name, base64_field = self._DOWNLOAD_MAP[(document_type, file_type)]
        endpoint_pattern = str(getattr(self.client, endpoint_attr, ''))
        endpoint = endpoint_pattern.format(number=number)
        payload_method = getattr(self.client, payload_method_name)

        try:
            payload = payload_method(number)
            data = payload.get('data', payload) if isinstance(payload, dict) else {}
            if not isinstance(data, dict):
                raise DescargaFacturaError('Factus devolvió una respuesta inválida para descarga.')
            filename = self._resolve_filename(data=data, number=number, file_type=file_type)
            content = self._decode_required_base64(data=data, field=base64_field, document_type=document_type, file_type=file_type)
        except FactusAPIError as exc:
            self._log_factus_error(exc=exc, endpoint=endpoint, number=number)
            raise

        persisted_path = ''
        if instance is not None:
            persisted_path = self._persist_local_file(
                instance=instance,
                document_type=document_type,
                file_type=file_type,
                filename=filename,
                content=content,
            )

        return DownloadedDocument(content=content, filename=filename, source='remote', local_path=persisted_path)

    def _resolve_filename(self, *, data: dict[str, Any], number: str, file_type: FileType) -> str:
        filename = Path(str(data.get('file_name') or data.get('filename') or f'{number}.{file_type}')).name
        return filename or f'{number}.{file_type}'

    def _decode_required_base64(
        self,
        *,
        data: dict[str, Any],
        field: str,
        document_type: DocumentType,
        file_type: FileType,
    ) -> bytes:
        encoded = str(data.get(field) or '').strip()
        if not encoded:
            raise DescargaFacturaError(
                f'Factus no devolvió {field} para {document_type}:{file_type}. '
                'La API de descargas retorna JSON base64, no binario directo.'
            )
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise DescargaFacturaError(
                f'Factus devolvió base64 inválido para {document_type}:{file_type} en el campo {field}.'
            ) from exc

    def _persist_local_file(
        self,
        *,
        instance: Any,
        document_type: DocumentType,
        file_type: FileType,
        filename: str,
        content: bytes,
    ) -> str:
        field_name = f'{file_type}_local_path'
        meta_fields = {field.name for field in getattr(instance._meta, 'fields', [])}
        if field_name not in meta_fields:
            return ''

        relative_path = (Path('facturas') / self._DOC_FOLDER[document_type] / file_type / Path(filename).name).as_posix()
        output = Path(settings.MEDIA_ROOT) / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)

        setattr(instance, field_name, relative_path)
        if 'updated_at' in meta_fields:
            instance.save(update_fields=[field_name, 'updated_at'])
        else:
            instance.save(update_fields=[field_name])
        return relative_path

    def _log_factus_error(self, *, exc: FactusAPIError, endpoint: str, number: str) -> None:
        logger.warning(
            'electronic_document.factus_error endpoint=%s status_code=%s number=%s body=%s',
            endpoint,
            getattr(exc, 'status_code', None),
            number,
            getattr(exc, 'provider_detail', '')[:500],
        )
