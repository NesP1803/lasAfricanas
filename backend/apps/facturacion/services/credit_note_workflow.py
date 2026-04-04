from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica, NotaCreditoDetalle, NotaCreditoElectronica
from apps.facturacion.services.electronic_state_machine import extract_bill_errors
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusPendingCreditNoteError
from apps.facturacion.services.factus_catalog_lookup import get_tribute_id, get_unit_measure_id
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.inventario.models import MovimientoInventario, Producto
from apps.ventas.models import DetalleVenta

FINAL_ACCEPTED_ELECTRONIC_STATES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}
ACTIVE_CREDIT_LOCAL_STATES = {'BORRADOR', 'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'}
APPLIED_EFFECTS_STATES = {'ACEPTADA'}
ALLOWED_INVOICE_STATES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}


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
        'bill_number': str(current.get('bill_number') or data.get('bill_number') or '').strip(),
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
        qty = _to_decimal(line['cantidad_a_acreditar'])
        balance = line_credit_balance(detalle)
        base = (qty * detalle.precio_unitario).quantize(Decimal('0.01'))
        tax = (base * detalle.iva_porcentaje / Decimal('100')).quantize(Decimal('0.01'))
        line_total = (base + tax).quantize(Decimal('0.01'))
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


def _build_reference_code(factura: FacturaElectronica, *, is_total: bool) -> str:
    tipo = 'TOTAL' if is_total else 'PARCIAL'
    return f'NC-{factura.id}-{tipo}'


def _map_payload_for_factus(factura: FacturaElectronica, motivo: str, preview_lines: list[dict[str, Any]], *, is_total: bool, client: FactusClient) -> dict[str, Any]:
    reference_payload = build_invoice_payload(factura.venta)
    local_customer = reference_payload.get('customer', {})
    reference_items = {str(item.get('code_reference') or ''): item for item in reference_payload.get('items', [])}
    bill_id, customer = _resolve_bill_id_and_customer(factura, client, local_customer=local_customer)
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
    return {
        'bill_id': bill_id,
        'customer': customer,
        'numbering_range_id': factura.response_json.get('data', {}).get('bill', {}).get('numbering_range_id'),
        'reference_code': _build_reference_code(factura, is_total=is_total),
        'correction_concept_code': 1 if is_total else 2,
        'credit_note_reason': motivo,
        'bill_number': factura.number,
        'reference_code_bill': factura.reference_code or factura.number,
        'reference_cufe': factura.cufe,
        'items': items,
    }


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
    if estado_electronico in FINAL_ACCEPTED_ELECTRONIC_STATES:
        nota.estado_local = 'ACEPTADA'
    elif estado_electronico == 'RECHAZADA':
        nota.estado_local = 'RECHAZADA'
    elif estado_electronico == 'ERROR_INTEGRACION':
        nota.estado_local = 'ERROR_INTEGRACION'
    else:
        has_evidence = any([fields['number'], fields['uuid'], fields['reference_code'], estado_raw])
        nota.estado_local = 'PENDIENTE_DIAN' if has_evidence else 'CONFLICTO_FACTUS'
    nota.save(update_fields=['number', 'uuid', 'cufe', 'pdf_url', 'xml_url', 'public_url', 'reference_code', 'status_raw_factus', 'remote_status_raw', 'estado_electronico', 'status', 'response_json', 'synchronized_at', 'estado_local', 'updated_at'])
    return nota


def _find_existing_open_note(factura: FacturaElectronica, *, tipo: str) -> NotaCreditoElectronica | None:
    return NotaCreditoElectronica.objects.filter(factura=factura, tipo_nota=tipo, estado_local__in=['BORRADOR', 'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS']).order_by('-created_at').first()


def _exact_match_remote_candidate(candidates: list[dict[str, Any]], *, reference_code: str, bill_number: str, number: str = '') -> dict[str, Any] | None:
    for item in candidates:
        if not isinstance(item, dict):
            continue
        f = extract_credit_note_remote_fields({'data': {'credit_note': item}})
        if reference_code and f['reference_code'] == reference_code:
            return item
        if bill_number and f['bill_number'] == str(bill_number):
            return item
        if number and f['number'] == number:
            return item
    return None


def _list_candidates(remote_list: dict[str, Any]) -> list[dict[str, Any]]:
    data = remote_list.get('data', remote_list)
    if isinstance(data, list):
        return [i for i in data if isinstance(i, dict)]
    if isinstance(data, dict):
        for key in ('credit_notes', 'data', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                return [i for i in value if isinstance(i, dict)]
    return []


def _try_reconcile_from_remote(factura: FacturaElectronica, *, reference_code: str, tipo_nota: str, number: str = '') -> NotaCreditoElectronica | None:
    client = FactusClient()
    try:
        remote_list = client.list_credit_notes(reference_code=reference_code, bill_number=factura.number, number=number or None)
    except Exception:
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
    estado_factura = factura.estado_electronico or factura.status
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
        recovered = _try_reconcile_from_remote(factura, reference_code=reference_code, tipo_nota=tipo_nota)
        if recovered:
            effects = _apply_business_effects_if_needed(recovered, user)
            return recovered, _build_result_meta(recovered, business_effects_applied=effects, warnings=['Factus respondió 409 y se reconcilió nota existente.'])
        nota.estado_local = 'PENDIENTE_DIAN'
        nota.codigo_error = 'FACTUS_409_PENDIENTE_DIAN'
        nota.mensaje_error = 'Factus reportó una nota pendiente por DIAN. Use sincronizar para confirmar el resultado final.'
        nota.synchronized_at = timezone.now()
        nota.save(update_fields=['estado_local', 'codigo_error', 'mensaje_error', 'synchronized_at', 'updated_at'])
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
    if not nota.number:
        reconciled = _try_reconcile_from_remote(nota.factura, reference_code=nota.reference_code, tipo_nota=nota.tipo_nota)
        if reconciled:
            return reconciled
        nota.estado_local = 'CONFLICTO_FACTUS'
        nota.codigo_error = 'FACTUS_SIN_NUMERO_CONFIRMADO'
        nota.mensaje_error = 'No existe número confirmado en Factus para esta nota. Debe conciliarse manualmente.'
        nota.synchronized_at = timezone.now()
        nota.save(update_fields=['estado_local', 'codigo_error', 'mensaje_error', 'synchronized_at', 'updated_at'])
        return nota
    client = FactusClient()
    try:
        remote = client.get_credit_note(nota.number)
        return _update_note_from_remote(nota, remote)
    except FactusAPIError as exc:
        if exc.status_code != 404:
            raise
        try:
            remote_list = client.list_credit_notes(number=nota.number, bill_number=nota.factura.number, reference_code=nota.reference_code)
        except Exception:
            remote_list = {}
        matched = _exact_match_remote_candidate(_list_candidates(remote_list), reference_code=nota.reference_code, bill_number=str(nota.factura.number or ''), number=str(nota.number or ''))
        if matched:
            return _update_note_from_remote(nota, {'data': {'credit_note': matched}})
        nota.estado_local = 'CONFLICTO_FACTUS'
        nota.codigo_error = 'FACTUS_SYNC_SIN_EVIDENCIA'
        nota.mensaje_error = 'Factus no permitió confirmar la nota (show/list sin resultado verificable exacto).'
        nota.synchronized_at = timezone.now()
        nota.save(update_fields=['estado_local', 'codigo_error', 'mensaje_error', 'synchronized_at', 'updated_at'])
        return nota


def sync_credit_note_with_effects(nota: NotaCreditoElectronica, *, user) -> tuple[NotaCreditoElectronica, bool]:
    synced = sync_credit_note(nota)
    effects = _apply_business_effects_if_needed(synced, user)
    return synced, effects
