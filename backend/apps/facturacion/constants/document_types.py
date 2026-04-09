"""Fuente única para tipos documentales locales y mapeo hacia Factus."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


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

DOCUMENT_TYPE_ALIASES: dict[str, set[str]] = {
    'FACTURA_VENTA': {
        'FACTURA_VENTA',
        'FACTURA DE VENTA',
        'FACTURA',
        'INVOICE',
        'BILL',
        '21',
    },
    'NOTA_CREDITO': {
        'NOTA_CREDITO',
        'NOTA CREDITO',
        'NOTA CREDITO',
        'CREDIT NOTE',
        'CREDIT_NOTE',
        'NC',
        '22',
    },
    'NOTA_DEBITO': {
        'NOTA_DEBITO',
        'NOTA DEBITO',
        'DEBIT NOTE',
        'DEBIT_NOTE',
        'ND',
        '23',
    },
    'DOCUMENTO_SOPORTE': {
        'DOCUMENTO_SOPORTE',
        'DOCUMENTO SOPORTE',
        'SUPPORT_DOCUMENT',
        'SUPPORT DOCUMENT',
        'DS',
        '24',
    },
    'NOTA_AJUSTE_DOCUMENTO_SOPORTE': {
        'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        'NOTA DE AJUSTE DOCUMENTO SOPORTE',
        'SUPPORT_DOCUMENT_ADJUSTMENT_NOTE',
        'NADS',
        '25',
    },
}


def normalize_document_token(raw_document: str) -> str:
    raw = str(raw_document or '').strip()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.upper().replace('-', ' ').replace('_', ' ')
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def normalize_local_document_code(raw_document: str, *, default: str = 'FACTURA_VENTA') -> str:
    compact = normalize_document_token(raw_document).replace(' ', '_')
    if compact in FACTUS_CODE_TO_LOCAL:
        return FACTUS_CODE_TO_LOCAL[compact]
    for local_code, aliases in DOCUMENT_TYPE_ALIASES.items():
        normalized_aliases = {normalize_document_token(alias).replace(' ', '_') for alias in aliases}
        normalized_aliases.add(local_code)
        if compact in normalized_aliases:
            return local_code
    if compact == 'PAYROLL':
        return 'NOMINA'
    if compact == 'PAYROLL_ADJUSTMENT_NOTE':
        return 'NOTA_AJUSTE_NOMINA'
    if compact in {'FACTURA_TALONARIO_PAPEL', 'FACTURA_TALONARIO_O_PAPEL', 'PAPER_INVOICE'}:
        return 'FACTURA_TALONARIO_O_PAPEL'
    return default


def document_matches_local_code(local_document_code: str, remote_document: str) -> bool:
    normalized_local = normalize_local_document_code(local_document_code, default='')
    if not normalized_local:
        return False
    normalized_remote = normalize_local_document_code(remote_document, default='')
    if normalized_remote:
        return normalized_remote == normalized_local
    token = normalize_document_token(remote_document)
    aliases = DOCUMENT_TYPE_ALIASES.get(normalized_local, {normalized_local})
    alias_tokens = {normalize_document_token(alias) for alias in aliases}
    alias_tokens.add(normalized_local)
    alias_tokens.add(str(LOCAL_TO_FACTUS_CODE.get(normalized_local, '')).strip())
    return token in alias_tokens
