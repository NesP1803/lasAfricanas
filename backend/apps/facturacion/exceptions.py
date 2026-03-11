"""Excepciones de dominio de facturación."""


class FacturaDuplicadaError(Exception):
    """Se lanza cuando se intenta generar una factura con un reference_code ya existente."""
