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


def resolve_api_version() -> str:
    version = str(config("FACTUS_API_VERSION", default="v2")).lower().strip()
    return version if version in DEFAULTS else "v2"


def get_endpoint(name: str, *, api_version: str | None = None) -> str:
    version = (api_version or resolve_api_version()).lower().strip()
    table = DEFAULTS.get(version, DEFAULTS["v2"])
    return table[name]
