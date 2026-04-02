"""Excepciones de dominio de facturación."""


class FacturaDuplicadaError(Exception):
    """Se lanza cuando se intenta generar una factura con un reference_code ya existente."""


class FacturaNoValidaParaNotaCredito(Exception):
    """Se lanza cuando una factura no está en estado válido para nota crédito."""


class DocumentoSoporteInvalido(Exception):
    """Se lanza cuando los datos del documento soporte no cumplen validaciones mínimas."""


class DocumentoSoporteNoValido(Exception):
    """Se lanza cuando un documento soporte no está en estado válido para nota de ajuste."""


class FacturaPersistenciaError(Exception):
    """Se lanza cuando falla la persistencia local de la factura electrónica."""
