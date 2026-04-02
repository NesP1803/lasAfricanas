"""Lookups de homologaciones/catálogos Factus."""

from __future__ import annotations

import unicodedata

from apps.facturacion_electronica.catalogos.models import (
    DocumentoIdentificacionFactus,
    MetodoPagoFactus,
    MunicipioFactus,
    TributoFactus,
    UnidadMedidaFactus,
)


DOCUMENT_TYPE_ALIASES: dict[str, str] = {
    'CC': 'CC',
    'CEDULA': 'CC',
    'CEDULA DE CIUDADANIA': 'CC',
    'NIT': 'NIT',
    'CE': 'CE',
    'CEDULA DE EXTRANJERIA': 'CE',
    'TI': 'TI',
    'TARJETA DE IDENTIDAD': 'TI',
    'PAS': 'PASAPORTE',
    'PASAPORTE': 'PASAPORTE',
    'PP': 'PASAPORTE',
    'PPT': 'PPT',
    'PEP': 'PEP',
}

DOCUMENT_TYPE_FACTUS_CODE_CANDIDATES: dict[str, tuple[str, ...]] = {
    # Códigos frecuentes DIAN/Factus por tipo.
    'CC': ('CC', '13'),
    'NIT': ('NIT', '31'),
    'CE': ('CE', '22'),
    'TI': ('TI', '12'),
    'PASAPORTE': ('PASAPORTE', 'PAS', '41'),
    'PEP': ('PEP', '47'),
    'PPT': ('PPT', '48'),
}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = text.strip().upper().replace('.', '').replace('-', ' ')
    return ' '.join(text.split())


def normalize_document_type_code(codigo: str) -> str:
    normalized = _normalize_text(codigo)
    return DOCUMENT_TYPE_ALIASES.get(normalized, normalized)


def get_municipality_id(codigo: str, default: int = 149) -> int:
    return (
        MunicipioFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )


def get_tribute_id(codigo: str, default: int = 1) -> int:
    return (
        TributoFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )


def get_payment_method_code(codigo: str, default: str = '10') -> str:
    return (
        MetodoPagoFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('codigo', flat=True)
        .first()
        or default
    )


def get_unit_measure_id(codigo: str, default: int = 70) -> int:
    return (
        UnidadMedidaFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
        or default
    )


def get_document_type_id(codigo: str, default: int = 3) -> int:
    normalized = normalize_document_type_code(codigo)
    if not normalized:
        return default

    candidates = list(DOCUMENT_TYPE_FACTUS_CODE_CANDIDATES.get(normalized, (normalized,)))
    if normalized not in candidates:
        candidates.insert(0, normalized)

    for candidate in candidates:
        factus_id = (
            DocumentoIdentificacionFactus.objects.filter(codigo__iexact=candidate, is_active=True)
            .values_list('factus_id', flat=True)
            .first()
        )
        if factus_id:
            return factus_id
    return default
