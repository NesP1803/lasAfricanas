"""Compatibilidad: builder unificado de payload de Factus."""

from apps.facturacion.services.factus_payload_builder import build_invoice_payload as build_payload_from_venta

__all__ = ['build_payload_from_venta']
