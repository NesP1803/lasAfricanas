"""Fuente única para tipos documentales locales y mapeo hacia Factus."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentType:
    key: str
    label: str
    factus_code: str


DOCUMENT_TYPES: tuple[DocumentType, ...] = (
    DocumentType('FACTURA_VENTA', 'Factura de venta', '21'),
    DocumentType('NOTA_CREDITO', 'Nota crédito', '22'),
    DocumentType('NOTA_DEBITO', 'Nota débito', '23'),
    DocumentType('DOCUMENTO_SOPORTE', 'Documento soporte', '24'),
    DocumentType('NOTA_AJUSTE_DOCUMENTO_SOPORTE', 'Nota de ajuste documento soporte', '25'),
    DocumentType('NOMINA', 'Nómina', '26'),
    DocumentType('NOTA_AJUSTE_NOMINA', 'Nota de ajuste nómina', '27'),
    DocumentType('FACTURA_TALONARIO_O_PAPEL', 'Factura de talonario o de papel', '30'),
)

LOCAL_TO_FACTUS_CODE: dict[str, str] = {item.key: item.factus_code for item in DOCUMENT_TYPES}
FACTUS_CODE_TO_LOCAL: dict[str, str] = {item.factus_code: item.key for item in DOCUMENT_TYPES}
LOCAL_LABELS: dict[str, str] = {item.key: item.label for item in DOCUMENT_TYPES}


def normalize_local_document_code(raw_document: str) -> str:
    compact = (
        str(raw_document or '')
        .strip()
        .upper()
        .replace('Á', 'A')
        .replace('É', 'E')
        .replace('Í', 'I')
        .replace('Ó', 'O')
        .replace('Ú', 'U')
        .replace('-', '_')
        .replace(' ', '_')
    )
    aliases = {
        'FACTURA': 'FACTURA_VENTA',
        'FACTURA_DE_VENTA': 'FACTURA_VENTA',
        'INVOICE': 'FACTURA_VENTA',
        'BILL': 'FACTURA_VENTA',
        'NOTA_CREDITO': 'NOTA_CREDITO',
        'CREDIT_NOTE': 'NOTA_CREDITO',
        'NC': 'NOTA_CREDITO',
        'NOTA_DEBITO': 'NOTA_DEBITO',
        'DEBIT_NOTE': 'NOTA_DEBITO',
        'DOCUMENTO_SOPORTE': 'DOCUMENTO_SOPORTE',
        'SUPPORT_DOCUMENT': 'DOCUMENTO_SOPORTE',
        'DS': 'DOCUMENTO_SOPORTE',
        'NOTA_AJUSTE_DOCUMENTO_SOPORTE': 'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        'SUPPORT_DOCUMENT_ADJUSTMENT_NOTE': 'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        'NADS': 'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        'NOMINA': 'NOMINA',
        'PAYROLL': 'NOMINA',
        'NOTA_AJUSTE_NOMINA': 'NOTA_AJUSTE_NOMINA',
        'PAYROLL_ADJUSTMENT_NOTE': 'NOTA_AJUSTE_NOMINA',
        'FACTURA_TALONARIO_PAPEL': 'FACTURA_TALONARIO_O_PAPEL',
        'FACTURA_TALONARIO_O_PAPEL': 'FACTURA_TALONARIO_O_PAPEL',
        'PAPER_INVOICE': 'FACTURA_TALONARIO_O_PAPEL',
    }
    if compact in FACTUS_CODE_TO_LOCAL:
        return FACTUS_CODE_TO_LOCAL[compact]
    return aliases.get(compact, 'FACTURA_VENTA')
