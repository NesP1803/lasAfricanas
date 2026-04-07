from __future__ import annotations

import logging
import time
from decimal import Decimal
from uuid import uuid4
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica, NotaCreditoDetalle, NotaCreditoElectronica
from apps.facturacion.services.electronic_state_machine import extract_bill_errors
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusPendingCreditNoteError
from apps.facturacion.services.factus_catalog_lookup import get_tribute_id, get_unit_measure_id
from apps.facturacion.services.factus_catalog_lookup import get_payment_method_code
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.document_totals import calculate_document_detail_totals, q_money, to_decimal
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.inventario.models import MovimientoInventario, Producto
from apps.ventas.models import DetalleVenta

logger = logging.getLogger(__name__)

FINAL_ACCEPTED_ELECTRONIC_STATES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}
ACTIVE_CREDIT_LOCAL_STATES = {'BORRADOR', 'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'}
APPLIED_EFFECTS_STATES = {'ACEPTADA'}
ALLOWED_INVOICE_STATES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}
CREDIT_NOTE_CUSTOMIZATION_ID = 20
SYNC_REFERENCE_POLL_ATTEMPTS = 5
SYNC_REFERENCE_POLL_SLEEP_SECONDS = 0.7
CREDIT_NOTE_CONCEPT_CODE_MAP = {
    'ANULACION_TOTAL': 1,
    'DEVOLUCION_PARCIAL': 2,
}


class CreditNoteValidationError(Exception):
    """Error de validación de negocio esperado para notas crédito."""


class CreditNoteStateError(CreditNoteValidationError):
    """Error de estado inválido del flujo de nota crédito."""


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value or '0'))


def extract_credit_note_remote_fields(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    current = data.get('credit_note', data) if isinstance(data, dict) else {}
    if not isinstance(current, dict):
        current = {}
    return {
        'number': str(current.get('number') or data.get('number') or '').strip(),
        'uuid': str(current.get('uuid') or data.get('uuid') or '').strip(),
        'cufe': str(current.get('cufe') or data.get('cufe') or '').strip(),
        'xml_url': str(current.get('xml_url') or data.get('xml_url') or '').strip(),
        'pdf_url': str(current.get('pdf_url') or data.get('pdf_url') or '').strip(),
        'public_url': str(current.get('public_url') or data.get('public_url') or '').strip(),
        'reference_code': str(current.get('reference_code') or data.get('reference_code') or '').strip(),
        'bill_number': str(
            current.get('bill_number')
            or current.get('number_bill')
            or data.get('bill_number')
            or data.get('number_bill')
            or ''
        ).strip(),
        'status_raw': str(current.get('status') or data.get('status') or response_json.get('status') or '').strip().lower(),
    }


def map_credit_note_status(response_json: dict[str, Any]) -> tuple[str, str]:
    fields = extract_credit_note_remote_fields(response_json)
    bill_errors = extract_bill_errors(response_json)
    raw = fields['status_raw']
    if fields['number'] and fields['cufe']:
        return ('ACEPTADA_CON_OBSERVACIONES' if bill_errors else 'ACEPTADA', raw or 'accepted')
    if raw in {'rejected', 'rechazada', 'failed'} or bill_errors:
        return 'RECHAZADA', raw or 'rejected'
    if raw in {'error', 'error_integracion'}:
        return 'ERROR_INTEGRACION', raw or 'error'
    return 'PENDIENTE_DIAN', raw or 'pending_dian'


def _active_credit_queryset(factura: FacturaElectronica):
    return NotaCreditoDetalle.objects.filter(
        nota_credito__factura=factura,
        nota_credito__estado_local__in=APPLIED_EFFECTS_STATES,
    )


def line_credit_balance(detalle_venta: DetalleVenta) -> dict[str, Decimal]:
    facturados = detalle_venta.cantidad
    acreditados = (
        NotaCreditoDetalle.objects.filter(
            detalle_venta_original=detalle_venta,
            nota_credito__estado_local__in=APPLIED_EFFECTS_STATES,
        )
        .values_list('cantidad_a_acreditar', flat=True)
    )
    ya_acreditado = sum(acreditados, Decimal('0'))
    disponible = facturados - ya_acreditado
    return {
        'cantidad_original': facturados,
        'cantidad_ya_acreditada': ya_acreditado,
        'cantidad_disponible': disponible,
    }


def _resolve_lines_for_credit(factura: FacturaElectronica, lines: list[dict[str, Any]], *, is_total: bool) -> list[dict[str, Any]]:
    detalles = {d.id: d for d in DetalleVenta.objects.select_related('producto').filter(venta=factura.venta)}
    if not detalles:
        raise CreditNoteValidationError('La factura no tiene líneas disponibles para acreditar.')

    if is_total:
        resolved: list[dict[str, Any]] = []
        for detalle in detalles.values():
            balance = line_credit_balance(detalle)
            disponible = balance['cantidad_disponible']
            if disponible <= 0:
                continue
            resolved.append(
                {
                    'detalle_venta_original_id': detalle.id,
                    'cantidad_a_acreditar': str(disponible),
                    'afecta_inventario': bool(lines[0].get('afecta_inventario', True)) if lines else True,
                    'motivo_linea': str(lines[0].get('motivo_linea', '') or '') if lines else '',
                }
            )
        if not resolved:
            raise CreditNoteStateError('La factura ya no tiene saldo disponible para una nota crédito total.')
        return resolved

    if not lines:
        raise CreditNoteValidationError('Debe enviar al menos una línea para acreditar.')

    resolved = []
    for line in lines:
        detalle_id = line.get('detalle_venta_original_id')
        detalle = detalles.get(detalle_id)
        if detalle is None:
            raise CreditNoteValidationError(f'La línea {detalle_id} no pertenece a la factura seleccionada.')
        qty = _to_decimal(line.get('cantidad_a_acreditar'))
        if qty <= 0:
            raise CreditNoteValidationError('La cantidad a acreditar debe ser mayor a cero.')
        balance = line_credit_balance(detalle)
        if qty > balance['cantidad_disponible']:
            raise CreditNoteValidationError(f'La línea {detalle.id} excede la cantidad disponible ({balance["cantidad_disponible"]}).')
        resolved.append(
            {
                'detalle_venta_original_id': detalle.id,
                'cantidad_a_acreditar': qty,
                'afecta_inventario': bool(line.get('afecta_inventario', False)),
                'motivo_linea': str(line.get('motivo_linea', '') or ''),
            }
        )
    return resolved


def build_credit_preview(factura: FacturaElectronica, lines: list[dict[str, Any]], *, is_total: bool = False) -> dict[str, Any]:
    resolved_lines = _resolve_lines_for_credit(factura, lines, is_total=is_total)
    preview_lines: list[dict[str, Any]] = []
    subtotal = Decimal('0')
    impuestos = Decimal('0')
    total = Decimal('0')
    unidades = Decimal('0')
    for line in resolved_lines:
        detalle = DetalleVenta.objects.select_related('producto').get(pk=line['detalle_venta_original_id'], venta=factura.venta)
        qty = to_decimal(line['cantidad_a_acreditar'])
        balance = line_credit_balance(detalle)
        totals = calculate_document_detail_totals(
            quantity=qty,
            unit_gross_price=detalle.precio_unitario,
            discount_pct=Decimal('0.00'),
            tax_pct=detalle.iva_porcentaje,
        )
        base = q_money(totals['base'])
        tax = q_money(totals['impuesto'])
        line_total = q_money(totals['total'])
        subtotal += base
        impuestos += tax
        total += line_total
        unidades += qty
        preview_lines.append(
            {
                'detalle_venta_original_id': detalle.id,
                'producto_id': detalle.producto_id,
                'producto': detalle.producto.nombre,
                'cantidad_original_facturada': str(detalle.cantidad),
                'cantidad_ya_acreditada': str(balance['cantidad_ya_acreditada']),
                'cantidad_disponible': str(balance['cantidad_disponible']),
                'cantidad_a_acreditar': str(qty),
                'precio_unitario': str(detalle.precio_unitario),
                'descuento': '0',
                'base_impuesto': str(base),
                'impuesto': str(tax),
                'total_linea': str(line_total),
                'afecta_inventario': bool(line.get('afecta_inventario', False)),
                'motivo_linea': str(line.get('motivo_linea', '') or ''),
            }
        )
    if not preview_lines:
        raise CreditNoteValidationError('No hay líneas efectivas para acreditar.')
    return {'lineas': preview_lines, 'subtotal': str(subtotal), 'impuestos': str(impuestos), 'total': str(total), 'unidades': str(unidades)}


def _apply_inventory_return(nota: NotaCreditoElectronica, user) -> None:
    detalles = list(nota.detalles.select_related('producto'))
    productos = {p.id: p for p in Producto.objects.select_for_update().filter(id__in=[d.producto_id for d in detalles])}
    for d in detalles:
        if not d.afecta_inventario:
            continue
        producto = productos[d.producto_id]
        stock_anterior = producto.stock
        stock_nuevo = stock_anterior + d.cantidad_a_acreditar
        MovimientoInventario.objects.create(
            producto=producto,
            tipo='DEVOLUCION',
            cantidad=d.cantidad_a_acreditar,
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo,
            costo_unitario=d.precio_unitario,
            usuario=user,
            referencia=f'NC-{nota.number or nota.id}',
            observaciones=f'Devolución por nota crédito {nota.number or nota.id}',
        )
        producto.stock = stock_nuevo
        producto.save(update_fields=['stock', 'updated_at'])


def _resolve_bill_id_and_customer(factura: FacturaElectronica, client: FactusClient, *, local_customer: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    response_json = factura.response_json if isinstance(factura.response_json, dict) else {}
    bill = response_json.get('data', response_json).get('bill', {}) if isinstance(response_json.get('data', response_json), dict) else {}
    bill_id = bill.get('id')
    if bill_id:
        return int(bill_id), local_customer
    if factura.number:
        remote = client.get_invoice(factura.number)
        remote_bill = remote.get('data', remote).get('bill', {}) if isinstance(remote.get('data', remote), dict) else {}
        remote_bill_id = remote_bill.get('id')
        if remote_bill_id:
            return int(remote_bill_id), local_customer
    raise CreditNoteValidationError('No fue posible identificar bill_id de la factura electrónica origen para emitir la nota crédito.')


def _resolve_customization_id(*, factura: FacturaElectronica) -> int:
    if not factura.emitida_en_factus:
        raise CreditNoteValidationError('La nota crédito solo se permite para facturas electrónicas emitidas.')
    return CREDIT_NOTE_CUSTOMIZATION_ID


def _resolve_correction_concept_code(*, concepto: str, is_total: bool) -> int:
    normalized = str(concepto or '').strip().upper()
    if not normalized:
        normalized = 'ANULACION_TOTAL' if is_total else 'DEVOLUCION_PARCIAL'
    code = CREDIT_NOTE_CONCEPT_CODE_MAP.get(normalized)
    if code is None:
        raise CreditNoteValidationError(f'Concepto fiscal de nota crédito inválido: {concepto!r}.')
    return int(code)


def _build_reference_code(factura: FacturaElectronica, *, is_total: bool) -> str:
    tipo = 'TOTAL' if is_total else 'PARCIAL'
    seed = uuid4().hex[:10].upper()
    return f'NC-{factura.id}-{tipo}-{seed}'


def _map_payload_for_factus(factura: FacturaElectronica, motivo: str, preview_lines: list[dict[str, Any]], *, is_total: bool, client: FactusClient) -> dict[str, Any]:
    reference_payload = build_invoice_payload(factura.venta)
    local_customer = reference_payload.get('customer', {})
    reference_items = {str(item.get('code_reference') or ''): item for item in reference_payload.get('items', [])}
    bill_id, customer = _resolve_bill_id_and_customer(factura, client, local_customer=local_customer)
    numbering_range = resolve_numbering_range(document_code='NOTA_CREDITO')
    numbering_range_id = int(numbering_range.factus_range_id or 0)
    if numbering_range_id <= 0:
        raise CreditNoteValidationError('El rango activo de nota crédito no tiene factus_range_id válido.')
    concepto = 'ANULACION_TOTAL' if is_total else 'DEVOLUCION_PARCIAL'
    reference_code = _build_reference_code(factura, is_total=is_total)
    logger.info(
        'facturacion.nota_credito.payload.range_selected factura_id=%s reference_code=%s numbering_range_id=%s factus_range_id=%s range_prefix=%s',
        factura.id,
        reference_code,
        numbering_range_id,
        numbering_range.factus_range_id,
        numbering_range.prefijo,
    )
    items = []
    for line in preview_lines:
        detalle = DetalleVenta.objects.select_related('producto').get(pk=line['detalle_venta_original_id'], venta=factura.venta)
        template = reference_items.get(str(detalle.producto.codigo or ''))
        tribute_default = get_tribute_id('ZZ' if _to_decimal(detalle.iva_porcentaje) == Decimal('0') else '01')
        items.append(
            {
                'code_reference': detalle.producto.codigo,
                'name': detalle.producto.nombre,
                'quantity': float(_to_decimal(line['cantidad_a_acreditar'])),
                'price': float(detalle.precio_unitario),
                'tax_rate': float(detalle.iva_porcentaje),
                'discount_rate': float(_to_decimal(line.get('descuento') or 0)),
                'unit_measure_id': int((template or {}).get('unit_measure_id') or get_unit_measure_id(detalle.producto.unidad_medida)),
                'standard_code_id': int((template or {}).get('standard_code_id') or 1),
                'tribute_id': int((template or {}).get('tribute_id') or tribute_default),
                'is_excluded': int((template or {}).get('is_excluded') or 0),
            }
        )
    payload = {
        'numbering_range_id': numbering_range_id,
        'correction_concept_code': _resolve_correction_concept_code(concepto=concepto, is_total=is_total),
        'customization_id': _resolve_customization_id(factura=factura),
        'bill_id': bill_id,
        'reference_code': reference_code,
        'payment_method_code': get_payment_method_code(factura.venta.medio_pago),
        'observation': str(motivo or '')[:250],
        'send_email': False,
        'items': items,
    }
    if customer:
        payload['customer'] = customer
    return payload


def _refresh_invoice_credit_status(factura: FacturaElectronica) -> None:
    total_facturado = sum((d.cantidad for d in factura.venta.detalles.all()), Decimal('0'))
    total_creditado = sum(_active_credit_queryset(factura).values_list('cantidad_a_acreditar', flat=True), Decimal('0'))
    estado = 'ACTIVA' if total_creditado <= 0 else ('CREDITADA_TOTAL' if total_creditado >= total_facturado else 'CREDITADA_PARCIAL')
    if factura.estado_acreditacion != estado:
        factura.estado_acreditacion = estado
        factura.save(update_fields=['estado_acreditacion', 'updated_at'])


def _apply_business_effects_if_needed(nota: NotaCreditoElectronica, user) -> bool:
    if nota.estado_local != 'ACEPTADA':
        _refresh_invoice_credit_status(nota.factura)
        return False
    with transaction.atomic():
        if not MovimientoInventario.objects.filter(referencia=f'NC-{nota.number or nota.id}', tipo='DEVOLUCION').exists():
            _apply_inventory_return(nota, user)
        _refresh_invoice_credit_status(nota.factura)
        if nota.tipo_nota == 'TOTAL':
            venta = nota.factura.venta
            if venta.estado != 'ANULADA':
                venta.estado = 'ANULADA'
                venta.save(update_fields=['estado', 'updated_at'])
    return True


def _update_note_from_remote(nota: NotaCreditoElectronica, remote: dict[str, Any]) -> NotaCreditoElectronica:
    fields = extract_credit_note_remote_fields(remote)
    estado_electronico, estado_raw = map_credit_note_status(remote)
    has_final_evidence = bool((fields['number'] or nota.number) and (fields['cufe'] or nota.cufe))
    nota.number = fields['number'] or nota.number
    nota.uuid = fields['uuid'] or nota.uuid
    nota.cufe = fields['cufe'] or nota.cufe
    nota.pdf_url = fields['pdf_url'] or nota.pdf_url
    nota.xml_url = fields['xml_url'] or nota.xml_url
    nota.public_url = fields['public_url'] or nota.public_url
    nota.reference_code = fields['reference_code'] or nota.reference_code
    nota.status_raw_factus = estado_raw
    nota.remote_status_raw = estado_raw
    nota.estado_electronico = estado_electronico
    nota.status = estado_electronico
    nota.response_json = remote
    nota.synchronized_at = timezone.now()
    nota.last_sync_at = nota.synchronized_at
    nota.remote_identifier = fields['uuid'] or fields['cufe'] or nota.remote_identifier
    nota.last_remote_error = ''
    logger.info(
        'facturacion.nota_credito.update_from_remote nota_credito_id=%s reference_code=%s remote_number=%s remote_uuid=%s remote_cufe=%s remote_status=%s',
        nota.id,
        nota.reference_code,
        fields['number'],
        fields['uuid'],
        fields['cufe'],
        estado_raw,
    )
    if estado_electronico in FINAL_ACCEPTED_ELECTRONIC_STATES or has_final_evidence:
        if estado_electronico not in FINAL_ACCEPTED_ELECTRONIC_STATES and has_final_evidence:
            estado_electronico = 'ACEPTADA'
            nota.estado_electronico = estado_electronico
            nota.status = estado_electronico
        nota.estado_local = 'ACEPTADA'
    elif estado_electronico == 'RECHAZADA':
        nota.estado_local = 'RECHAZADA'
    elif estado_electronico == 'ERROR_INTEGRACION':
        nota.estado_local = 'ERROR_INTEGRACION'
    else:
        has_evidence = any([fields['number'], fields['uuid'], fields['reference_code'], estado_raw])
        if nota.estado_local == 'ACEPTADA' and any([nota.number, nota.cufe]):
            logger.warning(
                'facturacion.nota_credito.update_from_remote.skip_degrade nota_credito_id=%s reference_code=%s current_state=%s remote_state=%s',
                nota.id,
                nota.reference_code,
                nota.estado_local,
                estado_raw,
            )
        else:
            nota.estado_local = 'PENDIENTE_DIAN' if has_evidence else 'CONFLICTO_FACTUS'
    sync_meta = dict(nota.sync_metadata or {})
    sync_meta.update(
        {
            'last_resolution': nota.estado_local,
            'last_remote_status': estado_raw,
            'last_reference_code': nota.reference_code,
            'last_number': nota.number,
            'updated_from_remote_at': timezone.now().isoformat(),
        }
    )
    nota.sync_metadata = sync_meta
    nota.save(update_fields=['number', 'uuid', 'cufe', 'pdf_url', 'xml_url', 'public_url', 'reference_code', 'status_raw_factus', 'remote_status_raw', 'estado_electronico', 'status', 'response_json', 'synchronized_at', 'last_sync_at', 'remote_identifier', 'last_remote_error', 'sync_metadata', 'estado_local', 'updated_at'])
    return nota


def _find_existing_open_note(factura: FacturaElectronica, *, tipo: str) -> NotaCreditoElectronica | None:
    return NotaCreditoElectronica.objects.filter(factura=factura, tipo_nota=tipo, estado_local__in=['BORRADOR', 'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS']).order_by('-created_at').first()


def _exact_match_remote_candidate(candidates: list[dict[str, Any]], *, reference_code: str, bill_number: str, number: str = '') -> dict[str, Any] | None:
    logger.info(
        'facturacion.nota_credito.sync.lookup_candidates reference_code=%s number=%s bill_number=%s total_candidates=%s',
        reference_code,
        number,
        bill_number,
        len(candidates),
    )
    if reference_code:
        for item in candidates:
            if not isinstance(item, dict):
                continue
            f = extract_credit_note_remote_fields({'data': {'credit_note': item}})
            if f['reference_code'] == reference_code:
                logger.info(
                    'facturacion.nota_credito.sync.match_by_reference_code reference_code=%s matched_number=%s matched_bill_number=%s',
                    reference_code,
                    f['number'],
                    f['bill_number'],
                )
                return item
    for item in candidates:
        if not isinstance(item, dict):
            continue
        f = extract_credit_note_remote_fields({'data': {'credit_note': item}})
        if number and f['number'] == number:
            logger.info(
                'facturacion.nota_credito.sync.match_by_number number=%s matched_reference_code=%s',
                number,
                f['reference_code'],
            )
            return item
    if bill_number and len(candidates) == 1 and not reference_code and not number:
        item = candidates[0]
        f = extract_credit_note_remote_fields({'data': {'credit_note': item}})
        if f['bill_number'] == str(bill_number):
            logger.info(
                'facturacion.nota_credito.sync.match_by_single_bill_number bill_number=%s matched_reference_code=%s matched_number=%s',
                bill_number,
                f['reference_code'],
                f['number'],
            )
            return item
    return None


def _list_candidates(remote_list: dict[str, Any]) -> list[dict[str, Any]]:
    data = remote_list.get('data', remote_list)
    if isinstance(data, dict):
        for key in ('credit_note',):
            value = data.get(key)
            if isinstance(value, dict):
                return [value]
    if isinstance(data, list):
        return [i for i in data if isinstance(i, dict)]
    if isinstance(data, dict):
        for key in ('credit_notes', 'data', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                return [i for i in value if isinstance(i, dict)]
            if isinstance(value, dict):
                nested_list = value.get('data')
                if isinstance(nested_list, list):
                    return [i for i in nested_list if isinstance(i, dict)]
    return []


def _poll_remote_credit_note_candidate(
    *,
    client: FactusClient,
    nota: NotaCreditoElectronica,
    reference_code: str,
    sync_meta: dict[str, Any],
    attempts: int = SYNC_REFERENCE_POLL_ATTEMPTS,
    sleep_seconds: float = SYNC_REFERENCE_POLL_SLEEP_SECONDS,
) -> tuple[dict[str, Any] | None, str]:
    bill_number = str(nota.factura.number or '')
    number = str(nota.number or '')
    list_error = ''
    for attempt in range(attempts):
        logger.info(
            'facturacion.nota_credito.sync.poll_by_reference_code nota_credito_id=%s reference_code=%s poll_attempt=%s total_attempts=%s',
            nota.id,
            reference_code,
            attempt + 1,
            attempts,
        )
        try:
            remote_list = client.get_credit_note_by_reference_code(reference_code, bill_number=nota.factura.number or None)
            candidates = _list_candidates(remote_list)
            logger.info(
                'facturacion.nota_credito.sync.poll_response nota_credito_id=%s reference_code=%s poll_attempt=%s candidates=%s raw=%s',
                nota.id,
                reference_code,
                attempt + 1,
                len(candidates),
                str(remote_list)[:1200],
            )
            sync_meta['last_lookup'] = 'list_credit_notes_polling'
            sync_meta['last_lookup_result_count'] = len(candidates)
            remote_candidate = _exact_match_remote_candidate(
                candidates,
                reference_code=reference_code,
                bill_number=bill_number,
                number=number,
            )
            if remote_candidate:
                return remote_candidate, ''
        except FactusAPIError as exc:
            sync_meta['last_poll_error'] = str(exc)
            logger.warning(
                'facturacion.nota_credito.sync.poll_error nota_credito_id=%s reference_code=%s poll_attempt=%s status_code=%s error=%s',
                nota.id,
                reference_code,
                attempt + 1,
                exc.status_code,
                str(exc),
            )
            if exc.status_code not in {404, 409}:
                list_error = str(exc)
                break
        if attempt < attempts - 1:
            time.sleep(sleep_seconds * (attempt + 1))
    return None, list_error


def _try_reconcile_from_remote(factura: FacturaElectronica, *, reference_code: str, tipo_nota: str, number: str = '') -> NotaCreditoElectronica | None:
    client = FactusClient()
    try:
        remote_list = client.list_credit_notes(reference_code=reference_code, bill_number=factura.number, number=number or None)
    except Exception as exc:
        logger.warning(
            'facturacion.nota_credito.reconcile_remote.error factura_id=%s reference_code=%s number=%s error=%s',
            factura.id,
            reference_code,
            number,
            str(exc),
        )
        return None
    matched = _exact_match_remote_candidate(_list_candidates(remote_list), reference_code=reference_code, bill_number=str(factura.number or ''), number=number)
    if not matched:
        return None
    nota = _find_existing_open_note(factura, tipo=tipo_nota)
    if nota is None:
        nota = NotaCreditoElectronica.objects.create(
            factura=factura,
            venta_origen=factura.venta,
            number=str(matched.get('number') or ''),
            tipo_nota=tipo_nota,
            concepto='ANULACION_TOTAL' if tipo_nota == 'TOTAL' else 'DEVOLUCION_PARCIAL',
            motivo='Nota reconciliada automáticamente desde Factus',
            estado_local='PENDIENTE_DIAN',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={},
            response_json={},
            reference_code=reference_code,
        )
    return _update_note_from_remote(nota, {'data': {'credit_note': matched}})


def sincronizar_nota_credito(nota_credito_id: int, *, user=None, force_retry: bool = False) -> NotaCreditoElectronica:
    with transaction.atomic():
        nota = (
            NotaCreditoElectronica.objects.select_for_update()
            .select_related('factura__venta')
            .get(pk=nota_credito_id)
        )
        reference_code = str(nota.reference_code or '').strip()
        if not reference_code:
            reference_code = f'NC-{nota.factura_id}-{nota.tipo_nota}-{nota.id}'
            nota.reference_code = reference_code
            nota.save(update_fields=['reference_code', 'updated_at'])

        client = FactusClient()
        sync_meta = dict(nota.sync_metadata or {})
        sync_meta['last_sync_started_at'] = timezone.now().isoformat()
        sync_meta['force_retry'] = bool(force_retry)
        sync_meta['attempts'] = int(sync_meta.get('attempts') or 0) + 1
        sync_meta['reference_code'] = reference_code

        remote_candidate: dict[str, Any] | None = None
        list_error = ''
        try:
            logger.info(
                'facturacion.nota_credito.sync.lookup_by_reference_code nota_credito_id=%s reference_code=%s bill_number=%s',
                nota.id,
                reference_code,
                nota.factura.number,
            )
            remote_list = client.get_credit_note_by_reference_code(reference_code, bill_number=nota.factura.number or None)
            candidates = _list_candidates(remote_list)
            logger.info(
                'facturacion.nota_credito.sync.lookup_response nota_credito_id=%s reference_code=%s candidates=%s raw=%s',
                nota.id,
                reference_code,
                len(candidates),
                str(remote_list)[:1200],
            )
            remote_candidate = _exact_match_remote_candidate(
                candidates,
                reference_code=reference_code,
                bill_number=str(nota.factura.number or ''),
                number=str(nota.number or ''),
            )
            sync_meta['last_lookup'] = 'list_credit_notes'
            sync_meta['last_lookup_result_count'] = len(candidates)
        except FactusAPIError as exc:
            if exc.status_code == 404:
                sync_meta['last_lookup_error'] = 'list_empty_or_not_found'
            else:
                list_error = str(exc)
                sync_meta['last_lookup_error'] = list_error

        if remote_candidate:
            logger.info(
                'facturacion.nota_credito.sync.resolved nota_credito_id=%s venta_id=%s factura_id=%s reference_code=%s endpoint=%s method=GET status_code=%s decision=%s',
                nota.id,
                nota.factura.venta_id,
                nota.factura_id,
                reference_code,
                client.credit_note_list_path,
                200,
                'remote_match_by_reference_code',
            )
            nota.sync_metadata = sync_meta
            nota = _update_note_from_remote(nota, {'data': {'credit_note': remote_candidate}})
            return nota

        if nota.number:
            try:
                logger.info(
                    'facturacion.nota_credito.sync.lookup_by_number nota_credito_id=%s number=%s',
                    nota.id,
                    nota.number,
                )
                remote = client.get_credit_note(nota.number)
                sync_meta['last_lookup'] = 'get_credit_note'
                logger.info(
                    'facturacion.nota_credito.sync.resolved nota_credito_id=%s venta_id=%s factura_id=%s reference_code=%s endpoint=%s method=GET status_code=%s decision=%s',
                    nota.id,
                    nota.factura.venta_id,
                    nota.factura_id,
                    reference_code,
                    client.credit_note_show_path.format(number=nota.number),
                    200,
                    'remote_match_by_number',
                )
                nota.sync_metadata = sync_meta
                return _update_note_from_remote(nota, remote)
            except FactusAPIError as exc:
                sync_meta['last_show_error'] = str(exc)
                if exc.status_code != 404:
                    raise

        if reference_code and nota.estado_local in {'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'}:
            remote_candidate, poll_error = _poll_remote_credit_note_candidate(
                client=client,
                nota=nota,
                reference_code=reference_code,
                sync_meta=sync_meta,
            )
            if remote_candidate:
                nota.sync_metadata = sync_meta
                return _update_note_from_remote(nota, {'data': {'credit_note': remote_candidate}})
            if poll_error:
                list_error = poll_error

        if isinstance(nota.request_json, dict) and nota.request_json:
            try:
                replay = client.create_and_validate_credit_note(nota.request_json)
                logger.info(
                    'facturacion.nota_credito.sync.replay_validate_ok nota_credito_id=%s reference_code=%s decision=%s',
                    nota.id,
                    reference_code,
                    'revalidated_with_same_reference_code',
                )
                nota.sync_metadata = sync_meta
                return _update_note_from_remote(nota, replay)
            except FactusPendingCreditNoteError:
                remote_candidate, poll_error = _poll_remote_credit_note_candidate(
                    client=client,
                    nota=nota,
                    reference_code=reference_code,
                    sync_meta=sync_meta,
                    attempts=SYNC_REFERENCE_POLL_ATTEMPTS + 1,
                    sleep_seconds=0.8,
                )
                if remote_candidate:
                    nota.sync_metadata = sync_meta
                    return _update_note_from_remote(nota, {'data': {'credit_note': remote_candidate}})
                if poll_error:
                    list_error = poll_error
                nota.estado_local = 'PENDIENTE_DIAN'
                nota.codigo_error = 'FACTUS_409_PENDIENTE_DIAN'
                nota.last_remote_error = 'Factus reporta nota pendiente por enviar/validar DIAN.'
                nota.mensaje_error = 'Factus confirmó que la nota sigue en proceso DIAN. Reintente sincronización.'
                nota.synchronized_at = timezone.now()
                nota.last_sync_at = nota.synchronized_at
                nota.sync_metadata = sync_meta
                nota.save(update_fields=['estado_local', 'codigo_error', 'last_remote_error', 'mensaje_error', 'synchronized_at', 'last_sync_at', 'sync_metadata', 'updated_at'])
                return nota
            except FactusAPIError as exc:
                if exc.status_code not in {404, 409}:
                    list_error = str(exc)

        nota.synchronized_at = timezone.now()
        nota.last_sync_at = nota.synchronized_at
        nota.sync_metadata = sync_meta
        if list_error:
            nota.estado_local = 'PENDIENTE_DIAN'
            nota.codigo_error = 'FACTUS_TIMEOUT_O_TRANSITORIO'
            nota.last_remote_error = list_error
            nota.mensaje_error = 'Factus no confirmó estado final. Reintente conciliación.'
        elif force_retry:
            nota.estado_local = 'CONFLICTO_FACTUS'
            nota.codigo_error = 'FACTUS_REINTENTO_SIN_EVIDENCIA'
            nota.last_remote_error = 'No hay evidencia remota por reference_code ni number.'
            nota.mensaje_error = 'Reintento ejecutado sin evidencia remota verificable; puede reconsultar o reemitir según política de negocio.'
        else:
            nota.estado_local = 'CONFLICTO_FACTUS'
            nota.codigo_error = 'FACTUS_SYNC_SIN_EVIDENCIA'
            nota.last_remote_error = 'No hay evidencia remota por reference_code.'
            nota.mensaje_error = 'Factus no confirmó el documento remoto. Use reintentar conciliación.'
        logger.warning(
            'facturacion.nota_credito.sync.unresolved nota_credito_id=%s venta_id=%s factura_id=%s reference_code=%s endpoint=%s method=GET status_code=%s decision=%s remote_error=%s',
            nota.id,
            nota.factura.venta_id,
            nota.factura_id,
            reference_code,
            client.credit_note_list_path,
            404 if not list_error else 502,
            nota.estado_local,
            nota.last_remote_error,
        )
        nota.save(update_fields=['estado_local', 'codigo_error', 'mensaje_error', 'synchronized_at', 'last_sync_at', 'last_remote_error', 'sync_metadata', 'updated_at'])
        return nota


def _poll_note_until_stable(nota: NotaCreditoElectronica, *, attempts: int = 4, sleep_seconds: float = 1.2) -> NotaCreditoElectronica:
    current = nota
    for _ in range(attempts):
        current = sync_credit_note(current)
        if current.estado_local in {'ACEPTADA', 'RECHAZADA', 'ERROR_INTEGRACION', 'CONFLICTO_FACTUS'}:
            return current
        time.sleep(sleep_seconds)
    return current


def _build_result_meta(nota: NotaCreditoElectronica, *, business_effects_applied: bool = False, warnings: list[str] | None = None) -> dict[str, Any]:
    result = 'error'
    http_status = 200
    if nota.estado_local == 'ACEPTADA':
        result = 'accepted'
        http_status = 200
    elif nota.estado_local == 'PENDIENTE_DIAN':
        result = 'pending_dian'
        http_status = 202
    elif nota.estado_local == 'RECHAZADA':
        result = 'rejected'
        http_status = 200
    elif nota.estado_local == 'CONFLICTO_FACTUS':
        result = 'conflict'
        http_status = 202
    elif nota.estado_local == 'ERROR_INTEGRACION':
        result = 'error'
        http_status = 502
    return {
        'ok': result in {'accepted', 'pending_dian'},
        'result': result,
        'finalized': result in {'accepted', 'rejected'},
        'business_effects_applied': business_effects_applied,
        'note_id': nota.id,
        'number': nota.number,
        'estado_local': nota.estado_local,
        'estado_electronico': nota.estado_electronico,
        'codigo_error': nota.codigo_error,
        'mensaje_error': nota.mensaje_error,
        'can_sync': nota.estado_local in {'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'},
        'can_retry': nota.estado_local in {'ERROR_INTEGRACION', 'CONFLICTO_FACTUS'},
        'warnings': warnings or [],
        'http_status': http_status,
    }


def create_credit_note(*, factura: FacturaElectronica, motivo: str, lines: list[dict[str, Any]], is_total: bool, user) -> tuple[NotaCreditoElectronica, dict[str, Any]]:
    if not factura.emitida_en_factus:
        raise CreditNoteStateError('La factura no está emitida electrónicamente; use anulación local.')
    estado_factura = factura.estado_electronico
    if estado_factura not in ALLOWED_INVOICE_STATES:
        raise CreditNoteStateError(f'La factura está en estado {estado_factura} y no admite nota crédito electrónica.')

    tipo_nota = 'TOTAL' if is_total else 'PARCIAL'
    existing_open = _find_existing_open_note(factura, tipo=tipo_nota)
    if existing_open:
        synced = _poll_note_until_stable(existing_open, attempts=2, sleep_seconds=0.5)
        effects = _apply_business_effects_if_needed(synced, user)
        return synced, _build_result_meta(synced, business_effects_applied=effects, warnings=['Ya existe una nota abierta para esta factura.'])

    client = FactusClient()
    preview = build_credit_preview(factura, lines, is_total=is_total)
    payload = _map_payload_for_factus(factura, motivo, preview['lineas'], is_total=is_total, client=client)
    reference_code = str(payload.get('reference_code') or '')
    range_trace = {
        'numbering_range_id': payload.get('numbering_range_id'),
        'document_code': 'NOTA_CREDITO',
        'range_prefix': '',
        'range_resolution': '',
    }
    try:
        selected_range = resolve_numbering_range(document_code='NOTA_CREDITO')
        range_trace['range_prefix'] = str(selected_range.prefijo or '')
        range_trace['range_resolution'] = str(selected_range.resolucion or '')
    except Exception:
        logger.warning(
            'facturacion.nota_credito.create.range_trace_unavailable factura_id=%s reference_code=%s',
            factura.id,
            reference_code,
        )
    payload['range_trace'] = range_trace

    with transaction.atomic():
        nota = NotaCreditoElectronica.objects.create(
            factura=factura,
            venta_origen=factura.venta,
            number='',
            tipo_nota=tipo_nota,
            concepto='ANULACION_TOTAL' if is_total else 'DEVOLUCION_PARCIAL',
            motivo=motivo,
            estado_local='PENDIENTE_ENVIO',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json=payload,
            response_json={},
            reference_code=reference_code,
            sync_metadata=range_trace,
        )
        for line in preview['lineas']:
            detalle = DetalleVenta.objects.get(pk=line['detalle_venta_original_id'])
            NotaCreditoDetalle.objects.create(
                nota_credito=nota,
                detalle_venta_original=detalle,
                producto_id=line['producto_id'],
                cantidad_original_facturada=_to_decimal(line['cantidad_original_facturada']),
                cantidad_ya_acreditada=_to_decimal(line['cantidad_ya_acreditada']),
                cantidad_a_acreditar=_to_decimal(line['cantidad_a_acreditar']),
                precio_unitario=_to_decimal(line['precio_unitario']),
                descuento=_to_decimal(line['descuento']),
                base_impuesto=_to_decimal(line['base_impuesto']),
                impuesto=_to_decimal(line['impuesto']),
                total_linea=_to_decimal(line['total_linea']),
                afecta_inventario=bool(line['afecta_inventario']),
                motivo_linea=str(line['motivo_linea']),
            )

    try:
        response = client.create_and_validate_credit_note(payload)
        nota = _update_note_from_remote(nota, response)
    except FactusPendingCreditNoteError:
        logger.warning(
            'facturacion.nota_credito.create.pending_409 factura_id=%s nota_credito_id=%s reference_code=%s',
            factura.id,
            nota.id,
            reference_code,
        )
        recovered = sincronizar_nota_credito(nota.id, user=user)
        recovered = _poll_note_until_stable(recovered, attempts=4, sleep_seconds=0.8)
        if recovered:
            effects = _apply_business_effects_if_needed(recovered, user)
            return recovered, _build_result_meta(recovered, business_effects_applied=effects, warnings=['Factus respondió 409 y se reconcilió nota existente.'])
        return nota, _build_result_meta(nota, warnings=['No se creó una nueva nota por idempotencia ante 409.'])
    except Exception as exc:
        nota.estado_local = 'ERROR_INTEGRACION'
        nota.mensaje_error = str(exc)
        nota.save(update_fields=['estado_local', 'mensaje_error', 'updated_at'])
        raise

    nota = _poll_note_until_stable(nota)
    effects = _apply_business_effects_if_needed(nota, user)
    return nota, _build_result_meta(nota, business_effects_applied=effects)


def sync_credit_note(nota: NotaCreditoElectronica) -> NotaCreditoElectronica:
    return sincronizar_nota_credito(nota.id)


def sync_credit_note_with_effects(nota: NotaCreditoElectronica, *, user) -> tuple[NotaCreditoElectronica, bool]:
    synced = sync_credit_note(nota)
    effects = _apply_business_effects_if_needed(synced, user)
    return synced, effects
