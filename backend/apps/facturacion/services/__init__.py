"""Servicios unificados de facturación electrónica Factus."""

from .facturar_venta import facturar_venta
from .sync_invoice_status import map_factus_status, sync_invoice_status
from .factus_client import (
    FactusAPIError,
    FactusAuthError,
    FactusClient,
    FactusPendingCreditNoteError,
    FactusValidationError,
)
from .exceptions import DescargaFacturaError, FacturaNoEncontrada, FactusConsultaError
from .factus_payload_builder import build_invoice_payload
from .credit_note_payload_builder import build_credit_note_payload
from .emitir_nota_credito import emitir_nota_credito
from .credit_note_workflow import (
    CreditNoteStateError,
    CreditNoteValidationError,
    build_credit_preview,
    create_credit_note,
    sync_credit_note,
)
from .support_document_payload_builder import build_support_document_payload
from .emitir_documento_soporte import emitir_documento_soporte
from .support_document_adjustment_payload_builder import build_adjustment_payload
from .emitir_nota_ajuste_documento_soporte import emitir_nota_ajuste_documento_soporte
from .download_invoice_files import download_pdf, download_xml
from .sync_numbering_ranges import sync_numbering_ranges
from .consecutivo_service import get_next_invoice_number
from .download_resource_files import DownloadResourceError, download_remote_file, read_local_media_file
from .emitir_factura_completa import emitir_factura_completa
from .pdf_personalizado import generar_pdf_personalizado

__all__ = [
    'FactusClient',
    'FactusAuthError',
    'FactusAPIError',
    'FactusValidationError',
    'FactusPendingCreditNoteError',
    'DescargaFacturaError',
    'FacturaNoEncontrada',
    'FactusConsultaError',
    'download_xml',
    'download_pdf',
    'build_invoice_payload',
    'build_credit_note_payload',
    'emitir_nota_credito',
    'CreditNoteValidationError',
    'CreditNoteStateError',
    'build_credit_preview',
    'create_credit_note',
    'sync_credit_note',
    'build_support_document_payload',
    'emitir_documento_soporte',
    'build_adjustment_payload',
    'emitir_nota_ajuste_documento_soporte',
    'facturar_venta',
    'map_factus_status',
    'sync_invoice_status',
    'sync_numbering_ranges',
    'get_next_invoice_number',
    'DownloadResourceError',
    'download_remote_file',
    'read_local_media_file',
    'emitir_factura_completa',
    'generar_pdf_personalizado',
]
