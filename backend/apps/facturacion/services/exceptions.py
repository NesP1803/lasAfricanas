"""Excepciones de dominio para sincronización de facturas electrónicas."""


class FacturaNoEncontrada(Exception):
    """Se lanza cuando no existe la factura electrónica consultada."""


class FactusConsultaError(Exception):
    """Error al consultar o sincronizar información de Factus."""
