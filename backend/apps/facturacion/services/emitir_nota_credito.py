"""Servicio legacy DEPRECATED: usar credit_note_workflow.create_credit_note."""

from __future__ import annotations

from apps.facturacion.services.factus_client import FactusValidationError


def emitir_nota_credito(*args, **kwargs):
    raise FactusValidationError('emitir_nota_credito está deprecado. Use el workflow create_credit_note.')
