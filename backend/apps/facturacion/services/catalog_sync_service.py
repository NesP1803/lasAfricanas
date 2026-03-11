"""Sincronización de catálogos Factus."""

from __future__ import annotations

from decouple import config
from django.db import transaction

from apps.facturacion.services.factus_client import FactusAPIError, FactusClient
from apps.facturacion_electronica.catalogos.models import (
    DocumentoIdentificacionFactus,
    MetodoPagoFactus,
    MunicipioFactus,
    TributoFactus,
    UnidadMedidaFactus,
)


class CatalogSyncService:
    def __init__(self) -> None:
        self.client = FactusClient()
        self.endpoints = {
            'municipalities': config('FACTUS_MUNICIPALITIES_PATH', default='/v1/municipalities'),
            'tributes': config('FACTUS_TRIBUTES_PATH', default='/v1/tributes'),
            'payment_methods': config('FACTUS_PAYMENT_METHODS_PATH', default='/v1/payment-methods'),
            'unit_measures': config('FACTUS_UNIT_MEASURES_PATH', default='/v1/unit-measures'),
            'identification_documents': config(
                'FACTUS_IDENTIFICATION_DOCUMENTS_PATH',
                default='/v1/identification-documents',
            ),
        }

    def _fetch_catalog(self, endpoint: str) -> list[dict]:
        payload = self.client.request('GET', endpoint)
        if isinstance(payload, list):
            return payload
        for key in ('data', 'results', 'items'):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        raise FactusAPIError(f'Formato de respuesta inesperado para catálogo Factus {endpoint}')

    @staticmethod
    def _normalize_item(item: dict) -> dict:
        factus_id = item.get('id') or item.get('factus_id')
        if factus_id is None:
            raise FactusAPIError('Elemento de catálogo sin identificador Factus')
        codigo = item.get('code') or item.get('codigo') or str(factus_id)
        nombre = item.get('name') or item.get('nombre') or codigo
        return {
            'factus_id': int(factus_id),
            'codigo': str(codigo).strip(),
            'nombre': str(nombre).strip(),
            'is_active': bool(item.get('is_active', True)),
        }

    def _sync_catalog(self, model, endpoint: str) -> dict:
        items = self._fetch_catalog(endpoint)
        normalized = [self._normalize_item(item) for item in items]
        current_ids = [item['factus_id'] for item in normalized]
        created = updated = 0
        with transaction.atomic():
            for item in normalized:
                _, was_created = model.objects.update_or_create(
                    factus_id=item['factus_id'],
                    defaults={
                        'codigo': item['codigo'],
                        'nombre': item['nombre'],
                        'is_active': item['is_active'],
                    },
                )
                created += int(was_created)
                updated += int(not was_created)

            deactivated = model.objects.exclude(factus_id__in=current_ids).filter(is_active=True).update(
                is_active=False
            )

        return {'fetched': len(normalized), 'created': created, 'updated': updated, 'deactivated': deactivated}

    def sync_municipalities(self) -> dict:
        return self._sync_catalog(MunicipioFactus, self.endpoints['municipalities'])

    def sync_tributes(self) -> dict:
        return self._sync_catalog(TributoFactus, self.endpoints['tributes'])

    def sync_payment_methods(self) -> dict:
        return self._sync_catalog(MetodoPagoFactus, self.endpoints['payment_methods'])

    def sync_unit_measures(self) -> dict:
        return self._sync_catalog(UnidadMedidaFactus, self.endpoints['unit_measures'])

    def sync_identification_documents(self) -> dict:
        return self._sync_catalog(DocumentoIdentificacionFactus, self.endpoints['identification_documents'])
