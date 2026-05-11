"""Registry de endpoints de Factus versionado por recurso."""

from __future__ import annotations

from decouple import config

DEFAULTS = {
    "v1": {
        "bill_validate": "/v1/bills/validate",
        "bill_show": "/v1/bills/show/{number}",
        "bill_list": "/v1/bills",
        "bill_download_pdf": "/v1/bills/download-pdf/{number}",
        "bill_download_xml": "/v1/bills/download-xml/{number}",
        "bill_send_email": "/v1/bills/send-email/{number}",
        "bill_email_content": "/v1/bills/{number}/email-content",
        "bill_delete_reference": "/v1/bills/reference/{reference_code}",
        "credit_note_validate": "/v1/credit-notes/validate",
        "credit_note_list": "/v1/credit-notes",
        "credit_note_show": "/v1/credit-notes/show/{number}",
        "credit_note_download_pdf": "/v1/credit-notes/download-pdf/{number}",
        "credit_note_download_xml": "/v1/credit-notes/download-xml/{number}",
        "credit_note_send_email": "/v1/credit-notes/send-email/{number}",
        "credit_note_email_content": "/v1/credit-notes/{number}/email-content",
        "credit_note_delete_reference": "/v1/credit-notes/reference/{reference_code}",
        "numbering_ranges": "/v1/numbering-ranges",
        "numbering_ranges_dian": "/v1/numbering-ranges/dian",
        "numbering_range_show": "/v1/numbering-ranges/{id}",
        "numbering_range_create": "/v1/numbering-ranges",
        "numbering_range_delete": "/v1/numbering-ranges/{id}",
        "numbering_range_update_current": "/v1/numbering-ranges/{id}/update-number",
        "support_document_validate": "/v1/support-documents/validate",
        "support_document_list": "/v1/support-documents",
        "support_document_show": "/v1/support-documents/show/{number}",
        "support_document_download_pdf": "/v1/support-documents/download-pdf/{number}",
        "support_document_download_xml": "/v1/support-documents/download-xml/{number}",
        "support_document_delete_reference": "/v1/support-documents/reference/{reference_code}",
        "support_adjustment_validate": "/v1/adjustment-notes/validate",
        "support_adjustment_list": "/v1/adjustment-notes",
        "support_adjustment_show": "/v1/adjustment-notes/show/{number}",
        "support_adjustment_download_pdf": "/v1/adjustment-notes/download-pdf/{number}",
        "support_adjustment_download_xml": "/v1/adjustment-notes/download-xml/{number}",
        "support_adjustment_delete_reference": "/v1/adjustment-notes/reference/{reference_code}",
        "bill_events": "/v1/bills/events/{number}",
        "bill_tacit_acceptance": "/v1/bills/acceptance-tacit/{number}",
        "bill_email_template": "/v1/bills/email-template/{number}",
        "bill_custom_pdf_upload": "/v1/bills/custom-pdf/{number}",
        "company_show": "/v1/company",
        "company_update": "/v1/company",
        "company_update_logo": "/v1/company/update-image",
        "countries": "/v1/countries",
        "municipalities": "/v1/municipalities",
        "tributes_products": "/v1/tributes/products",
        "unit_measures": "/v1/measurement-units",
        "reference_tables": "/v1/reference-tables",
        "customers_lookup": "/v1/customers",
        "document_receptions": "/v1/document-receptions",
        "subscriptions": "/v1/subscriptions",
    },
    "v2": {
        "bill_validate": "/v2/bills/validate",
        "bill_show": "/v2/bills/{number}",
        "bill_list": "/v2/bills",
        "bill_download_pdf": "/v2/bills/{number}/download-pdf",
        "bill_download_xml": "/v2/bills/{number}/download-xml/",
        "bill_send_email": "/v2/bills/{number}/send-email",
        "bill_email_content": "/v2/bills/{number}/email-content",
        "bill_delete_reference": "/v2/bills/destroy/reference/{reference_code}",
        "credit_note_validate": "/v2/credit-notes/validate",
        "credit_note_list": "/v2/credit-notes",
        "credit_note_show": "/v2/credit-notes/{number}",
        "credit_note_download_pdf": "/v2/credit-notes/{number}/download-pdf",
        "credit_note_download_xml": "/v2/credit-notes/{number}/download-xml/",
        "credit_note_send_email": "/v2/credit-notes/{number}/send-email",
        "credit_note_email_content": "/v2/credit-notes/{number}/email-content",
        "credit_note_delete_reference": "/v2/credit-notes/destroy/reference/{reference_code}",
        "numbering_ranges": "/v2/numbering-ranges",
        "numbering_ranges_dian": "/v2/numbering-ranges/dian",
    },
}

FALLBACK_TO_V1 = {
    name for name in DEFAULTS["v1"].keys() if name not in DEFAULTS["v2"]
}


def resolve_api_version() -> str:
    version = str(config("FACTUS_API_VERSION", default="v2")).lower().strip()
    return version if version in DEFAULTS else "v2"


def get_endpoint(name: str, *, api_version: str | None = None) -> str:
    version = (api_version or resolve_api_version()).lower().strip()
    table = DEFAULTS.get(version, DEFAULTS["v2"])
    if name in table:
        return table[name]
    if version == "v2" and name in FALLBACK_TO_V1:
        return DEFAULTS["v1"][name]
    raise KeyError(f"Endpoint '{name}' no está registrado para versión '{version}'")
