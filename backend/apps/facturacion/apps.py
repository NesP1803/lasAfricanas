import os

from django.apps import AppConfig


FACTUS_V2_ENDPOINT_DEFAULTS = {
    # Facturas V2
    'FACTUS_INVOICE_PATH': '/v2/bills/validate',
    'FACTUS_BILLS_LIST_PATH': '/v2/bills',
    'FACTUS_BILL_SHOW_PATH': '/v2/bills/{number}',
    'FACTUS_BILL_DOWNLOAD_PDF_PATH': '/v2/bills/{number}/download-pdf',
    'FACTUS_BILL_DOWNLOAD_XML_PATH': '/v2/bills/{number}/download-xml/',
    'FACTUS_BILL_EMAIL_CONTENT_PATH': '/v2/bills/{number}/email-content',
    'FACTUS_BILL_SEND_EMAIL_PATH': '/v2/bills/{number}/send-email',
    'FACTUS_BILL_DELETE_BY_REFERENCE_PATH': '/v2/bills/destroy/reference/{reference_code}',
    'FACTUS_BILL_EVENTS_PATH': '/v2/bills/{number}/radian/events',
    'FACTUS_BILL_TACIT_ACCEPTANCE_PATH': '/v2/bills/{number}/radian/events/{event_type}',
    'FACTUS_BILL_EMAIL_TEMPLATE_PATH': '/v2/bills/{number}/email-content',

    # Notas crédito V2
    'FACTUS_CREDIT_NOTE_PATH': '/v2/credit-notes/validate',
    'FACTUS_CREDIT_NOTES_LIST_PATH': '/v2/credit-notes',
    'FACTUS_CREDIT_NOTE_SHOW_PATH': '/v2/credit-notes/{number}',
    'FACTUS_CREDIT_NOTE_DOWNLOAD_PDF_PATH': '/v2/credit-notes/{number}/download-pdf',
    'FACTUS_CREDIT_NOTE_DOWNLOAD_XML_PATH': '/v2/credit-notes/{number}/download-xml/',
    'FACTUS_CREDIT_NOTE_EMAIL_CONTENT_PATH': '/v2/credit-notes/{number}/email-content',
    'FACTUS_CREDIT_NOTE_SEND_EMAIL_PATH': '/v2/credit-notes/{number}/send-email',
    'FACTUS_CREDIT_NOTE_DELETE_BY_REFERENCE_PATH': '/v2/credit-notes/destroy/reference/{reference_code}',

    # Rangos de numeración V2
    'FACTUS_NUMBERING_RANGES_PATH': '/v2/numbering-ranges',
    'FACTUS_NUMBERING_RANGE_SHOW_PATH': '/v2/numbering-ranges/{id}',
    'FACTUS_NUMBERING_RANGE_CREATE_PATH': '/v2/numbering-ranges',
    'FACTUS_NUMBERING_RANGE_DELETE_PATH': '/v2/numbering-ranges/{id}',
    'FACTUS_NUMBERING_RANGE_UPDATE_PATH': '/v2/numbering-ranges/{id}/update-number',
    'FACTUS_NUMBERING_RANGES_DIAN_PATH': '/v2/numbering-ranges/dian',

    # Empresa, catálogos y servicios auxiliares V2
    'FACTUS_COMPANY_SHOW_PATH': '/v2/company',
    'FACTUS_COMPANY_UPDATE_PATH': '/v2/company',
    'FACTUS_COMPANY_UPDATE_LOGO_PATH': '/v2/company/update-image',
    'FACTUS_CUSTOMERS_LOOKUP_PATH': '/v2/customers',
    'FACTUS_DOCUMENT_RECEPTIONS_PATH': '/v2/document-receptions',
    'FACTUS_SUBSCRIPTIONS_PATH': '/v2/subscriptions',
    'FACTUS_REFERENCE_TABLES_PATH': '/v2/reference-tables',
    'FACTUS_COUNTRIES_PATH': '/v2/countries',
    'FACTUS_MUNICIPALITIES_PATH': '/v2/municipalities',
    'FACTUS_MEASUREMENT_UNITS_PATH': '/v2/measurement-units',
    'FACTUS_TRIBUTES_PATH': '/v2/tributes/products',

    # Documentos soporte y notas de ajuste: la documentación oficial vigente
    # enlazada por el proyecto aún publica endpoints /v1 para estos recursos.
    'FACTUS_SUPPORT_DOCUMENT_VALIDATE_PATH': '/v1/support-documents/validate',
    'FACTUS_SUPPORT_DOCUMENTS_LIST_PATH': '/v1/support-documents',
    'FACTUS_SUPPORT_DOCUMENT_SHOW_PATH': '/v1/support-documents/show/{number}',
    'FACTUS_SUPPORT_DOCUMENT_DOWNLOAD_PDF_PATH': '/v1/support-documents/download-pdf/{number}',
    'FACTUS_SUPPORT_DOCUMENT_DOWNLOAD_XML_PATH': '/v1/support-documents/download-xml/{number}',
    'FACTUS_SUPPORT_DOCUMENT_DELETE_BY_REFERENCE_PATH': '/v1/support-documents/reference/{reference_code}',
    'FACTUS_SUPPORT_ADJUSTMENT_NOTE_VALIDATE_PATH': '/v1/adjustment-notes/validate',
    'FACTUS_SUPPORT_ADJUSTMENT_NOTES_LIST_PATH': '/v1/adjustment-notes',
    'FACTUS_SUPPORT_ADJUSTMENT_NOTE_SHOW_PATH': '/v1/adjustment-notes/show/{number}',
    'FACTUS_SUPPORT_ADJUSTMENT_NOTE_DOWNLOAD_PDF_PATH': '/v1/adjustment-notes/download-pdf/{number}',
    'FACTUS_SUPPORT_ADJUSTMENT_NOTE_DOWNLOAD_XML_PATH': '/v1/adjustment-notes/download-xml/{number}',
    'FACTUS_SUPPORT_ADJUSTMENT_NOTE_DELETE_BY_REFERENCE_PATH': '/v1/adjustment-notes/reference/{reference_code}',
}


def apply_factus_endpoint_defaults() -> None:
    """Deja Factus V2 como contrato activo sin eliminar rollback a V1.

    El cliente legado lee variables FACTUS_* con python-decouple. Por eso se
    inyectan aquí los endpoints oficiales V2 antes de instanciar FactusClient.
    Para volver temporalmente al contrato anterior, usar FACTUS_API_VERSION=v1.
    """
    version = str(os.environ.get('FACTUS_API_VERSION', 'v2') or 'v2').strip().lower()
    os.environ.setdefault('FACTUS_API_VERSION', version)
    if version != 'v2':
        return
    for key, value in FACTUS_V2_ENDPOINT_DEFAULTS.items():
        os.environ[key] = value


class FacturacionConfig(AppConfig):
    """Configuración de la app de facturación electrónica."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.facturacion'
    verbose_name = 'Facturación electrónica'

    def ready(self) -> None:
        apply_factus_endpoint_defaults()
