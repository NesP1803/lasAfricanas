"""Servicios de integración para facturación electrónica."""

from .factus_service import FactusServiceError, send_invoice_to_factus

__all__ = ['FactusServiceError', 'send_invoice_to_factus']
