"""Compatibilidad temporal: redirige al servicio unificado."""

from apps.facturacion.services.facturar_venta import facturar_venta
from apps.facturacion.services.factus_client import FactusAPIError as FactusServiceError


__all__ = ['FactusServiceError', 'facturar_venta']
