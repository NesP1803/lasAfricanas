from __future__ import annotations

import logging

from django.db import transaction

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.electronic_state_machine import extract_bill_errors as _extract_bill_errors
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusAPIError, FactusAuthError, FactusClient
from apps.facturacion.services.generate_qr_dian import generate_qr_dian
from apps.facturacion.services.persistence import assign_qr_image_fields, build_attempt_trace
from apps.facturacion.services.persistence_safety import log_model_string_overflow_diagnostics
from apps.facturacion.services.reconciliation import (
    PERSISTABLE_FACTURA_FIELDS,
    assert_emitted_document_matches_sale,
    extract_factus_data,
    merge_factus_fields,
)
from apps.usuarios.models import Usuario
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def sync_existing_pending_invoice(
    *,
    factura: FacturaElectronica,
    venta: Venta,
    triggered_by: Usuario | None,
) -> FacturaElectronica:
    """Intenta sincronizar una factura EN_PROCESO existente sin reenviar."""
    if not factura.number:
        return factura
    client = FactusClient()
    try:
        response = client.get_invoice(factura.number)
    except (FactusAPIError, FactusAuthError):
        logger.info(
            'facturar_venta.pending_sync_no_disponible venta_id=%s numero=%s',
            venta.id,
            factura.number,
        )
        return factura

    fields = extract_factus_data(response)
    assert_emitted_document_matches_sale(
        venta=venta,
        fields=fields,
        expected_number=factura.number or str(venta.numero_comprobante or ''),
        expected_reference_code=factura.reference_code or str(venta.numero_comprobante or ''),
    )
    bill_errors = _extract_bill_errors(response)
    missing_after_show = [field for field in ['xml_url', 'pdf_url'] if not fields.get(field)]
    if missing_after_show:
        try:
            response_download = client.get_invoice_downloads(factura.number)
            fields = merge_factus_fields(fields, extract_factus_data(response_download))
            assert_emitted_document_matches_sale(
                venta=venta,
                fields=fields,
                expected_number=factura.number or str(venta.numero_comprobante or ''),
                expected_reference_code=factura.reference_code or str(venta.numero_comprobante or ''),
            )
            if not bill_errors:
                bill_errors = _extract_bill_errors(response_download)
        except (FactusAPIError, FactusAuthError):
            logger.info(
                'facturar_venta.pending_sync_download_no_disponible venta_id=%s numero=%s',
                venta.id,
                factura.number,
            )
    persistable_fields = {k: v for k, v in fields.items() if k in PERSISTABLE_FACTURA_FIELDS}
    with transaction.atomic():
        locked = FacturaElectronica.objects.select_for_update().get(pk=factura.pk)
        for key, value in persistable_fields.items():
            if value:
                if key == 'qr':
                    locked.qr_data = value
                elif key == 'qr_image':
                    assign_qr_image_fields(locked, value)
                else:
                    setattr(locked, key, value)
        locked.estado_electronico = locked.status
        locked.emitida_en_factus = bool(locked.number and locked.cufe)
        locked.codigo_error = response.get('error_code') or locked.codigo_error
        locked.mensaje_error = '; '.join(bill_errors) if bill_errors else (response.get('error_message') or locked.mensaje_error)
        locked.response_json = build_attempt_trace(
            factura=locked,
            payload={},
            numero=locked.number or factura.number,
            reference_code=locked.reference_code or factura.reference_code or '',
            triggered_by=triggered_by,
            status=locked.status,
            response=response,
            final_fields={**fields, 'persisted_fields': persistable_fields, 'source': 'get_invoice_on_pending'},
            bill_errors=bill_errors,
        )
        log_model_string_overflow_diagnostics(
            instance=locked, venta_id=venta.id, factura_id=locked.pk, stage='sync_existing_pending_invoice'
        )
        locked.save(update_fields=['status', 'estado_electronico', 'cufe', 'uuid', 'number', 'reference_code', 'xml_url', 'pdf_url', 'public_url', 'qr_data', 'qr_image_url', 'qr_image_data', 'codigo_error', 'mensaje_error', 'response_json', 'updated_at'])
        logger.info(
            'facturar_venta.pending_sync_result venta_id=%s numero=%s status=%s',
            venta.id,
            locked.number,
            locked.status,
        )
        if locked.status == 'ACEPTADA' and locked.cufe and locked.number and not locked.qr:
            qr_file = generate_qr_dian(locked.number, locked.cufe)
            locked.qr.save(qr_file.name, qr_file, save=False)
            locked.save(update_fields=['qr', 'updated_at'])
        try:
            if locked.xml_url:
                download_xml(locked)
        except DescargaFacturaError:
            logger.warning(
                'facturar_venta.pending_sync_xml_descarga_error venta_id=%s factura=%s',
                venta.id,
                locked.number,
                exc_info=True,
            )
        try:
            if locked.pdf_url:
                download_pdf(locked)
        except DescargaFacturaError:
            logger.warning(
                'facturar_venta.pending_sync_pdf_descarga_error venta_id=%s factura=%s',
                venta.id,
                locked.number,
                exc_info=True,
            )
        return locked
