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
    sincronizar_nota_credito,
    sync_credit_note,
    sync_credit_note_with_effects,
)
from .support_document_payload_builder import build_support_document_payload
from .emitir_documento_soporte import emitir_documento_soporte
from .support_document_adjustment_payload_builder import build_adjustment_payload
from .emitir_nota_ajuste_documento_soporte import emitir_nota_ajuste_documento_soporte
from .download_invoice_files import download_pdf, download_xml
from .factura_assets_service import (
    decode_base64_file,
    store_factura_email_zip,
    store_factura_pdf,
    store_factura_xml,
    sync_invoice_assets,
)
from .sync_numbering_ranges import sync_numbering_ranges
from .consecutivo_service import get_next_invoice_number
from .download_resource_files import DownloadResourceError, download_remote_file, read_local_media_file
from .emitir_factura_completa import emitir_factura_completa
from .pdf_personalizado import generar_pdf_personalizado
from .upload_custom_pdf_to_factus import send_invoice_email_via_factus, upload_custom_pdf_to_factus
from .public_invoice_url import resolve_public_invoice_url
from .invoice_email_delete_service import delete_invoice_in_factus, get_invoice_email_content, send_invoice_email
from .numbering_range_admin_service import (
    create_range,
    delete_range,
    get_range,
    get_software_ranges,
    list_ranges,
    sync_ranges_to_db,
    update_range_current,
)

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
    'decode_base64_file',
    'store_factura_pdf',
    'store_factura_xml',
    'store_factura_email_zip',
    'sync_invoice_assets',
    'build_invoice_payload',
    'build_credit_note_payload',
    'emitir_nota_credito',
    'CreditNoteValidationError',
    'CreditNoteStateError',
    'build_credit_preview',
    'create_credit_note',
    'sincronizar_nota_credito',
    'sync_credit_note',
    'sync_credit_note_with_effects',
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
    'upload_custom_pdf_to_factus',
    'send_invoice_email_via_factus',
    'resolve_public_invoice_url',
    'get_invoice_email_content',
    'send_invoice_email',
    'delete_invoice_in_factus',
    'list_ranges',
    'get_range',
    'create_range',
    'delete_range',
    'update_range_current',
    'get_software_ranges',
    'sync_ranges_to_db',
]
