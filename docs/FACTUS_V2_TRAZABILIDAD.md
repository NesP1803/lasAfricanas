# Matriz de trazabilidad Factus v2 (base técnica)

| Endpoint lógico | Ruta v2 registrada | Método/cliente | Estado |
|---|---|---|---|
| bill_validate | `/v2/bills/validate` | `FactusClient.invoice_path` | OK |
| bill_show | `/v2/bills/{number}` | `FactusClient.bill_show_path` | OK |
| bill_list | `/v2/bills` | `FactusClient.bills_list_path` | OK |
| bill_download_pdf | `/v2/bills/{number}/download-pdf` | `FactusClient.bill_download_pdf_path` | OK |
| bill_download_xml | `/v2/bills/{number}/download-xml/` | `FactusClient.bill_download_xml_path` | OK |
| document_download_xml_attached | `/v2/documents/{number}/download-xml-attacheddocument/` | `FactusClient.document_download_xml_attached_path` | OK |
| credit_note_validate | `/v2/credit-notes/validate` | `FactusClient.credit_note_path` | OK |
| support_document_validate | `/v2/support-documents/validate` | `FactusClient.support_document_validate_path` | OK |
| support_adjustment_validate | `/v2/adjustment-notes/validate` | `FactusClient.support_adjustment_note_validate_path` | OK |
| numbering_range_change_status | `/v2/numbering-ranges/{id}/change-state` | `get_endpoint()` | OK |

> Esta matriz queda como base y se puede ampliar con servicios, vistas y tests por flujo funcional.
