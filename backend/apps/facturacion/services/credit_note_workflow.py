from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica, NotaCreditoDetalle, NotaCreditoElectronica
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.electronic_state_machine import map_factus_status
from apps.facturacion.services.factus_client import FactusClient, FactusPendingCreditNoteError
from apps.facturacion.services.factus_catalog_lookup import get_tribute_id, get_unit_measure_id
from apps.inventario.models import MovimientoInventario, Producto
from apps.ventas.models import DetalleVenta


ACTIVE_CREDIT_LOCAL_STATES = {'BORRADOR', 'PENDIENTE_ENVIO', 'EN_PROCESO', 'ACEPTADA'}
ALLOWED_INVOICE_STATES = {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}


class CreditNoteValidationError(Exception):
    """Error de validación de negocio esperado para notas crédito."""


class CreditNoteStateError(CreditNoteValidationError):
    """Error de estado inválido del flujo de nota crédito."""


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value or '0'))


def _active_credit_queryset(factura: FacturaElectronica):
    return NotaCreditoDetalle.objects.filter(
        nota_credito__factura=factura,
        nota_credito__estado_local__in=ACTIVE_CREDIT_LOCAL_STATES,
    )


def line_credit_balance(detalle_venta: DetalleVenta) -> dict[str, Decimal]:
    facturados = detalle_venta.cantidad
    acreditados = (
        NotaCreditoDetalle.objects.filter(
            detalle_venta_original=detalle_venta,
            nota_credito__estado_local__in=ACTIVE_CREDIT_LOCAL_STATES,
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
    detalles = {
        d.id: d
        for d in DetalleVenta.objects.select_related('producto').filter(venta=factura.venta)
    }
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
            raise CreditNoteValidationError(
                f'La línea {detalle_id} no pertenece a la factura seleccionada.'
            )
        qty = _to_decimal(line.get('cantidad_a_acreditar'))
        if qty <= 0:
            raise CreditNoteValidationError('La cantidad a acreditar debe ser mayor a cero.')
        balance = line_credit_balance(detalle)
        if qty > balance['cantidad_disponible']:
            raise CreditNoteValidationError(
                f'La línea {detalle.id} excede la cantidad disponible ({balance["cantidad_disponible"]}).'
            )
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

    return {
        'lineas': preview_lines,
        'subtotal': str(subtotal),
        'impuestos': str(impuestos),
        'total': str(total),
        'unidades': str(unidades),
    }


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
            referencia=f'NC-{nota.number}',
            observaciones=f'Devolución por nota crédito {nota.number}',
        )
        producto.stock = stock_nuevo
        producto.save(update_fields=['stock', 'updated_at'])


def _resolve_bill_id_and_customer(
    factura: FacturaElectronica,
    client: FactusClient,
    *,
    local_customer: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    response_json = factura.response_json if isinstance(factura.response_json, dict) else {}
    data = response_json.get('data', response_json)
    bill = data.get('bill', {}) if isinstance(data, dict) else {}
    bill_id = bill.get('id')

    if bill_id:
        return int(bill_id), local_customer

    if factura.number:
        remote = client.get_invoice(factura.number)
        remote_data = remote.get('data', remote)
        remote_bill = remote_data.get('bill', {}) if isinstance(remote_data, dict) else {}
        remote_bill_id = remote_bill.get('id')
        if remote_bill_id:
            return int(remote_bill_id), local_customer

    if not bill_id:
        raise CreditNoteValidationError(
            'No fue posible identificar bill_id de la factura electrónica origen para emitir la nota crédito.'
        )
    return int(bill_id), local_customer


def _build_reference_code(factura: FacturaElectronica, *, is_total: bool) -> str:
    tipo = 'TOTAL' if is_total else 'PARCIAL'
    return f'NC-{factura.id}-{tipo}'


def _map_payload_for_factus(
    factura: FacturaElectronica,
    motivo: str,
    preview_lines: list[dict[str, Any]],
    *,
    is_total: bool,
    client: FactusClient,
) -> dict[str, Any]:
    reference_payload = build_invoice_payload(factura.venta)
    local_customer = reference_payload.get('customer', {})
    reference_items = {
        str(item.get('code_reference') or ''): item
        for item in reference_payload.get('items', [])
    }
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

    if total_creditado <= 0:
        estado = 'ACTIVA'
    elif total_creditado >= total_facturado:
        estado = 'CREDITADA_TOTAL'
    else:
        estado = 'CREDITADA_PARCIAL'

    if factura.estado_acreditacion != estado:
        factura.estado_acreditacion = estado
        factura.save(update_fields=['estado_acreditacion', 'updated_at'])


def _update_note_from_remote(nota: NotaCreditoElectronica, remote: dict[str, Any]) -> NotaCreditoElectronica:
    data = remote.get('data', remote)
    current = data.get('credit_note', data)
    estado_electronico, estado_raw = map_factus_status(remote)
    nota.number = str(current.get('number') or nota.number)
    nota.uuid = str(current.get('uuid') or '') or None
    nota.cufe = str(current.get('cufe') or '') or None
    nota.pdf_url = str(current.get('pdf_url') or '') or nota.pdf_url
    nota.xml_url = str(current.get('xml_url') or '') or nota.xml_url
    nota.public_url = str(current.get('public_url') or '') or nota.public_url
    nota.status_raw_factus = estado_raw
    nota.remote_status_raw = estado_raw
    nota.estado_electronico = estado_electronico
    nota.status = estado_electronico
    nota.response_json = remote
    nota.synchronized_at = timezone.now()
    if estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
        nota.estado_local = 'ACEPTADA'
    elif estado_electronico == 'RECHAZADA':
        nota.estado_local = 'RECHAZADA'
    else:
        nota.estado_local = 'EN_PROCESO'
    nota.save(
        update_fields=[
            'number', 'uuid', 'cufe', 'pdf_url', 'xml_url', 'public_url',
            'status_raw_factus', 'remote_status_raw', 'estado_electronico', 'status',
            'response_json', 'synchronized_at', 'estado_local', 'updated_at'
        ]
    )
    _refresh_invoice_credit_status(nota.factura)
    return nota


def _find_existing_open_note(factura: FacturaElectronica, *, tipo: str) -> NotaCreditoElectronica | None:
    return (
        NotaCreditoElectronica.objects
        .filter(factura=factura, tipo_nota=tipo, estado_local__in=['BORRADOR', 'PENDIENTE_ENVIO', 'EN_PROCESO', 'ACEPTADA'])
        .order_by('-created_at')
        .first()
    )


def _try_reconcile_from_remote(factura: FacturaElectronica, *, reference_code: str, tipo_nota: str) -> NotaCreditoElectronica | None:
    client = FactusClient()
    try:
        remote_list = client.list_credit_notes(reference_code=reference_code, bill_number=factura.number)
    except Exception:
        remote_list = {}
    data = remote_list.get('data', remote_list)
    candidates = []
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        for key in ('credit_notes', 'data', 'items'):
            value = data.get(key)
            if isinstance(value, list):
                candidates = value
                break
    if not candidates:
        return None

    matched = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if str(item.get('reference_code') or '') == reference_code or str(item.get('bill_number') or '') == str(factura.number):
            matched = item
            break
    if matched is None:
        matched = candidates[0]

    number = str(matched.get('number') or '').strip()
    if not number:
        return None

    nota = _find_existing_open_note(factura, tipo=tipo_nota)
    if nota is None:
        nota = NotaCreditoElectronica.objects.create(
            factura=factura,
            venta_origen=factura.venta,
            number=number,
            tipo_nota=tipo_nota,
            concepto='ANULACION_TOTAL' if tipo_nota == 'TOTAL' else 'DEVOLUCION_PARCIAL',
            motivo='Nota reconciliada automáticamente desde Factus',
            estado_local='EN_PROCESO',
            estado_electronico='PENDIENTE_REINTENTO',
            status='PENDIENTE_REINTENTO',
            request_json={},
            response_json={},
            reference_code=reference_code,
        )
    nota.number = number
    nota.reference_code = reference_code
    nota.save(update_fields=['number', 'reference_code', 'updated_at'])
    return sync_credit_note(nota)


def create_credit_note(*, factura: FacturaElectronica, motivo: str, lines: list[dict[str, Any]], is_total: bool, user) -> tuple[NotaCreditoElectronica, dict[str, Any]]:
    if not factura.emitida_en_factus:
        raise CreditNoteStateError('La factura no está emitida electrónicamente; use anulación local.')

    estado_factura = factura.estado_electronico or factura.status
    if estado_factura not in ALLOWED_INVOICE_STATES:
        raise CreditNoteStateError(
            f'La factura está en estado {estado_factura} y no admite nota crédito electrónica.'
        )

    tipo_nota = 'TOTAL' if is_total else 'PARCIAL'
    existing_open = _find_existing_open_note(factura, tipo=tipo_nota)
    if existing_open and existing_open.estado_local in {'EN_PROCESO', 'ACEPTADA'}:
        synced = sync_credit_note(existing_open)
        return synced, {'result': 'already_exists_reconciled', 'http_status': 200}

    client = FactusClient()
    preview = build_credit_preview(factura, lines, is_total=is_total)
    payload = _map_payload_for_factus(factura, motivo, preview['lineas'], is_total=is_total, client=client)
    reference_code = str(payload.get('reference_code') or '')

    with transaction.atomic():
        nota = existing_open
        if nota is None:
            nota = NotaCreditoElectronica.objects.create(
                factura=factura,
                venta_origen=factura.venta,
                number=f'NC-PEND-{factura.id}-{int(timezone.now().timestamp())}',
                tipo_nota=tipo_nota,
                concepto='ANULACION_TOTAL' if is_total else 'DEVOLUCION_PARCIAL',
                motivo=motivo,
                estado_local='PENDIENTE_ENVIO',
                estado_electronico='PENDIENTE_REINTENTO',
                status='PENDIENTE_REINTENTO',
                request_json=payload,
                response_json={},
                reference_code=reference_code,
            )
        else:
            nota.motivo = motivo
            nota.request_json = payload
            nota.reference_code = reference_code
            nota.estado_local = 'PENDIENTE_ENVIO'
            nota.save(update_fields=['motivo', 'request_json', 'reference_code', 'estado_local', 'updated_at'])

        if not nota.detalles.exists():
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
            return recovered, {'result': 'factus_pending_recovered', 'http_status': 200}
        reconciled = _find_existing_open_note(factura, tipo=tipo_nota)
        if reconciled and reconciled.number and not reconciled.number.startswith('NC-PEND-'):
            try:
                reconciled = sync_credit_note(reconciled)
                return reconciled, {'result': 'factus_pending_reconciled', 'http_status': 200}
            except Exception:
                pass
        nota.estado_local = 'EN_PROCESO'
        nota.mensaje_error = 'Factus reportó una nota crédito pendiente por envío a DIAN. Quedó pendiente de sincronización.'
        nota.codigo_error = 'FACTUS_409_PENDING_DIAN'
        nota.synchronized_at = timezone.now()
        nota.save(update_fields=['estado_local', 'mensaje_error', 'codigo_error', 'synchronized_at', 'updated_at'])
        return nota, {'result': 'factus_pending_manual_sync', 'http_status': 202}
    except Exception as exc:
        nota.estado_local = 'ERROR_INTEGRACION'
        nota.mensaje_error = str(exc)
        nota.save(update_fields=['estado_local', 'mensaje_error', 'updated_at'])
        raise

    if nota.estado_local in {'ACEPTADA', 'EN_PROCESO'}:
        _apply_inventory_return(nota, user)
    _refresh_invoice_credit_status(factura)
    return nota, {'result': 'created', 'http_status': 201}


def sync_credit_note(nota: NotaCreditoElectronica) -> NotaCreditoElectronica:
    if not nota.number or nota.number.startswith('NC-PEND-'):
        nota.estado_local = 'EN_PROCESO'
        nota.synchronized_at = timezone.now()
        nota.save(update_fields=['estado_local', 'synchronized_at', 'updated_at'])
        return nota
    remote = FactusClient().get_credit_note(nota.number)
    return _update_note_from_remote(nota, remote)
