from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.facturacion.models import FacturaElectronica, NotaCreditoDetalle, NotaCreditoElectronica
from apps.facturacion.services.facturar_venta import map_factus_status
from apps.facturacion.services.factus_client import FactusClient
from apps.inventario.models import MovimientoInventario, Producto
from apps.ventas.models import DetalleVenta


ACTIVE_CREDIT_LOCAL_STATES = {'BORRADOR', 'ENVIADA_A_FACTUS', 'ACEPTADA'}
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


def _map_payload_for_factus(factura: FacturaElectronica, motivo: str, preview_lines: list[dict[str, Any]], *, is_total: bool) -> dict[str, Any]:
    items = []
    for line in preview_lines:
        detalle = DetalleVenta.objects.select_related('producto').get(pk=line['detalle_venta_original_id'], venta=factura.venta)
        items.append(
            {
                'code_reference': detalle.producto.codigo,
                'name': detalle.producto.nombre,
                'quantity': float(_to_decimal(line['cantidad_a_acreditar'])),
                'price': float(detalle.precio_unitario),
                'tax_rate': float(detalle.iva_porcentaje),
                'discount_rate': float(_to_decimal(line.get('descuento') or 0)),
            }
        )

    return {
        'numbering_range_id': factura.response_json.get('data', {}).get('bill', {}).get('numbering_range_id'),
        'reference_code': f'NC-{factura.number}-{timezone.now().strftime("%Y%m%d%H%M%S")}',
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


def create_credit_note(*, factura: FacturaElectronica, motivo: str, lines: list[dict[str, Any]], is_total: bool, user) -> NotaCreditoElectronica:
    if not factura.emitida_en_factus:
        raise CreditNoteStateError('La factura no está emitida electrónicamente; use anulación local.')

    estado_factura = factura.estado_electronico or factura.status
    if estado_factura not in ALLOWED_INVOICE_STATES:
        raise CreditNoteStateError(
            f'La factura está en estado {estado_factura} y no admite nota crédito electrónica.'
        )

    preview = build_credit_preview(factura, lines, is_total=is_total)
    payload = _map_payload_for_factus(factura, motivo, preview['lineas'], is_total=is_total)
    client = FactusClient()

    with transaction.atomic():
        nota = NotaCreditoElectronica.objects.create(
            factura=factura,
            venta_origen=factura.venta,
            number=f'NC-PEND-{factura.id}-{int(timezone.now().timestamp())}',
            tipo_nota='TOTAL' if is_total else 'PARCIAL',
            concepto='ANULACION_TOTAL' if is_total else 'DEVOLUCION_PARCIAL',
            motivo=motivo,
            estado_local='BORRADOR',
            estado_electronico='PENDIENTE_REINTENTO',
            status='PENDIENTE_REINTENTO',
            request_json=payload,
            response_json={},
            reference_code=str(payload.get('reference_code') or ''),
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
        data = response.get('data', response)
        credit_note = data.get('credit_note', data)
        nota.number = str(credit_note.get('number') or nota.number)
        nota.uuid = str(credit_note.get('uuid') or '') or None
        nota.cufe = str(credit_note.get('cufe') or '') or None
        nota.pdf_url = str(credit_note.get('pdf_url') or '') or None
        nota.xml_url = str(credit_note.get('xml_url') or '') or None
        nota.public_url = str(credit_note.get('public_url') or '') or None
        nota.status_raw_factus = str(credit_note.get('status') or data.get('status') or '')
        nota.estado_electronico = map_factus_status(response)
        nota.status = nota.estado_electronico
        has_emission_artifacts = bool(nota.number and nota.cufe)
        if nota.estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'} or has_emission_artifacts:
            nota.estado_local = 'ACEPTADA'
        else:
            nota.estado_local = 'ENVIADA_A_FACTUS'
        nota.response_json = response
        nota.save()
    except Exception as exc:
        nota.estado_local = 'ERROR_INTEGRACION'
        nota.mensaje_error = str(exc)
        nota.save(update_fields=['estado_local', 'mensaje_error', 'updated_at'])
        raise

    if nota.estado_local in {'ACEPTADA', 'ENVIADA_A_FACTUS'}:
        _apply_inventory_return(nota, user)
    _refresh_invoice_credit_status(factura)
    return nota


def sync_credit_note(nota: NotaCreditoElectronica) -> NotaCreditoElectronica:
    remote = FactusClient().get_credit_note(nota.number)
    data = remote.get('data', remote)
    current = data.get('credit_note', data)
    nota.status_raw_factus = str(current.get('status') or '')
    nota.estado_electronico = map_factus_status(remote)
    nota.status = nota.estado_electronico
    nota.response_json = remote
    if nota.estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
        nota.estado_local = 'ACEPTADA'
    elif nota.estado_electronico == 'RECHAZADA':
        nota.estado_local = 'RECHAZADA'
    else:
        nota.estado_local = 'ENVIADA_A_FACTUS'
    nota.save(update_fields=['status_raw_factus', 'estado_electronico', 'status', 'response_json', 'estado_local', 'updated_at'])
    _refresh_invoice_credit_status(nota.factura)
    return nota
