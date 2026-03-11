"""Compatibilidad: lookups de catálogos movidos a apps.facturacion.services."""

from apps.facturacion.services.factus_catalog_lookup import (
    get_document_type_id as get_identification_document_id,
    get_municipality_id,
    get_payment_method_code,
    get_tribute_id,
    get_unit_measure_id,
)

__all__ = [
    'get_municipality_id',
    'get_tribute_id',
    'get_unit_measure_id',
    'get_payment_method_code',
    'get_identification_document_id',
]
