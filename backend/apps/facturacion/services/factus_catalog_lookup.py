"""Lookups de homologaciones/catálogos Factus con estrategia unificada."""

from __future__ import annotations

import unicodedata

from apps.facturacion_electronica.catalogos.models import (
    DocumentoIdentificacionFactus,
    MetodoPagoFactus,
    MunicipioFactus,
    TributoFactus,
    UnidadMedidaFactus,
)
from apps.facturacion_electronica.models import (
    HomologacionMedioPago,
    HomologacionMunicipio,
    HomologacionTributo,
    HomologacionUnidadMedida,
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


def _bootstrap_minimum_catalogs() -> None:
    """Semillas mínimas locales para evitar bloqueos por catálogos vacíos."""
    DocumentoIdentificacionFactus.objects.update_or_create(
        factus_id=3,
        defaults={'codigo': '13', 'nombre': 'Cédula de ciudadanía', 'is_active': True},
    )
    DocumentoIdentificacionFactus.objects.update_or_create(
        factus_id=6,
        defaults={'codigo': '31', 'nombre': 'NIT', 'is_active': True},
    )
    MetodoPagoFactus.objects.update_or_create(
        factus_id=10,
        defaults={'codigo': '10', 'nombre': 'Efectivo', 'is_active': True},
    )
    MunicipioFactus.objects.update_or_create(
        factus_id=149,
        defaults={'codigo': '47001', 'nombre': 'Santa Marta', 'is_active': True},
    )
    TributoFactus.objects.update_or_create(
        factus_id=1,
        defaults={'codigo': '01', 'nombre': 'IVA', 'is_active': True},
    )
    TributoFactus.objects.update_or_create(
        factus_id=21,
        defaults={'codigo': 'ZZ', 'nombre': 'No causa', 'is_active': True},
    )
    UnidadMedidaFactus.objects.update_or_create(
        factus_id=70,
        defaults={'codigo': '94', 'nombre': 'Unidad', 'is_active': True},
    )


def _homologacion_lookup(model, field_name: str, codigo: str):
    normalized = _normalize_text(codigo)
    if not normalized:
        return None
    return (
        model.objects.filter(codigo_interno__iexact=normalized, is_active=True)
        .values_list(field_name, flat=True)
        .first()
    )


def get_municipality_id(codigo: str, default: int = 149) -> int:
    by_homologacion = _homologacion_lookup(HomologacionMunicipio, 'municipality_id', codigo)
    if by_homologacion:
        return int(by_homologacion)
    value = (
        MunicipioFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
    )
    return int(value or default)


def get_tribute_id(codigo: str, default: int = 1) -> int:
    by_homologacion = _homologacion_lookup(HomologacionTributo, 'tribute_id', codigo)
    if by_homologacion:
        return int(by_homologacion)
    value = (
        TributoFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
    )
    return int(value or default)


def get_first_active_tribute_id(default: int = 1) -> int:
    value = (
        TributoFactus.objects.filter(is_active=True)
        .order_by('factus_id')
        .values_list('factus_id', flat=True)
        .first()
    )
    return int(value or default)


def get_payment_method_code(codigo: str, default: str = '10') -> str:
    by_homologacion = _homologacion_lookup(HomologacionMedioPago, 'payment_method_code', codigo)
    if by_homologacion:
        return str(by_homologacion)
    value = (
        MetodoPagoFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('codigo', flat=True)
        .first()
    )
    return str(value or default)


def get_unit_measure_id(codigo: str, default: int = 70) -> int:
    by_homologacion = _homologacion_lookup(HomologacionUnidadMedida, 'unit_measure_id', codigo)
    if by_homologacion:
        return int(by_homologacion)
    value = (
        UnidadMedidaFactus.objects.filter(codigo=str(codigo), is_active=True)
        .values_list('factus_id', flat=True)
        .first()
    )
    return int(value or default)


def get_document_type_id(codigo: str, default: int = 3, seed_if_missing: bool = False) -> int:
    normalized = normalize_document_type_code(codigo)
    if not normalized:
        return default

    def _resolve() -> int:
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
                return int(factus_id)
        return 0

    result = _resolve()
    if result:
        return result
    if seed_if_missing:
        _bootstrap_minimum_catalogs()
        result = _resolve()
        if result:
            return result
    return default
