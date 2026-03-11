"""Compatibilidad: sincronización de catálogos en apps.facturacion.services."""

from apps.facturacion.services.catalog_sync_service import CatalogSyncService

_service = CatalogSyncService()


def sync_municipalities() -> dict:
    return _service.sync_municipalities()


def sync_tributes() -> dict:
    return _service.sync_tributes()


def sync_payment_methods() -> dict:
    return _service.sync_payment_methods()


def sync_unit_measures() -> dict:
    return _service.sync_unit_measures()


def sync_identification_documents() -> dict:
    return _service.sync_identification_documents()
