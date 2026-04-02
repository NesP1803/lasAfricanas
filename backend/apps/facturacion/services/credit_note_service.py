from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.facturacion.models import FacturaElectronica, NotaCreditoDetalle, NotaCreditoElectronica
from apps.facturacion.services.facturar_venta import map_factus_status
from apps.facturacion.services.factus_client import FactusClient
from apps.inventario.models import MovimientoInventario, Producto
from apps.ventas.models import DetalleVenta


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value or '0'))


def _factura_credit_totals(factura: FacturaElectronica) -> tuple[Decimal, Decimal]:
    total_facturado = Decimal('0')
    total_creditado = Decimal('0')
    for detalle in factura.venta.detalles.all():
        total_facturado += detalle.cantidad
    credit_rows = NotaCreditoDetalle.objects.filter(
        nota_credito__factura=factura,
        nota_credito__estado_local__in={'ENVIADA_A_FACTUS', 'ACEPTADA'},
    )
    for row in credit_rows:
        total_creditado += row.cantidad_a_acreditar
    return total_facturado, total_creditado


def line_credit_balance(detalle_venta: DetalleVenta) -> dict[str, Decimal]:
    facturados = detalle_venta.cantidad
    acreditados = (
        NotaCreditoDetalle.objects.filter(
            detalle_venta_original=detalle_venta,
            nota_credito__estado_local__in={'ENVIADA_A_FACTUS', 'ACEPTADA'},
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


def build_credit_preview(factura: FacturaElectronica, lines: list[dict[str, Any]]) -> dict[str, Any]:
    preview_lines: list[dict[str, Any]] = []
    total_base = Decimal('0')
    total_tax = Decimal('0')
    total = Decimal('0')
    for line in lines:
        detalle = DetalleVenta.objects.select_related('producto').get(pk=line['detalle_venta_original_id'], venta=factura.venta)
        qty = _to_decimal(line['cantidad_a_acreditar'])
        balance = line_credit_balance(detalle)
        if qty <= 0:
            raise ValidationError('La cantidad a acreditar debe ser mayor a cero.')
        if qty > balance['cantidad_disponible']:
            raise ValidationError(f'La línea {detalle.id} excede la cantidad disponible por acreditar.')
        base = qty * detalle.precio_unitario
        tax = (base * detalle.iva_porcentaje / Decimal('100')).quantize(Decimal('0.01'))
        line_total = base + tax
        total_base += base
        total_tax += tax
        total += line_total
        preview_lines.append({
            'detalle_venta_original_id': detalle.id,
            'producto_id': detalle.producto_id,
            'producto': detalle.producto.nombre,
            'cantidad_original_facturada': str(detalle.cantidad),
            'cantidad_ya_acreditada': str(balance['cantidad_ya_acreditada']),
            'cantidad_disponible': str(balance['cantidad_disponible']),
            'cantidad_a_acreditar': str(qty),
            'base_impuesto': str(base),
            'impuesto': str(tax),
            'total_linea': str(line_total),
            'afecta_inventario': bool(line.get('afecta_inventario', False)),
            'motivo_linea': str(line.get('motivo_linea', '') or ''),
        })
    return {'lineas': preview_lines, 'totales': {'base': str(total_base), 'impuesto': str(total_tax), 'total': str(total)}}


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


def _map_payload_for_factus(factura: FacturaElectronica, motivo: str, lines: list[dict[str, Any]], *, is_total: bool) -> dict[str, Any]:
    items = []
    for line in lines:
        detalle = DetalleVenta.objects.select_related('producto').get(pk=line['detalle_venta_original_id'], venta=factura.venta)
        qty = _to_decimal(line['cantidad_a_acreditar'])
        items.append({
            'code_reference': detalle.producto.codigo,
            'name': detalle.producto.nombre,
            'quantity': float(qty),
            'price': float(detalle.precio_unitario),
            'tax_rate': float(detalle.iva_porcentaje),
            'discount_rate': 0,
        })
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


def create_credit_note(*, factura: FacturaElectronica, motivo: str, lines: list[dict[str, Any]], is_total: bool, user) -> NotaCreditoElectronica:
    if not factura.emitida_en_factus:
        raise ValidationError('La factura no está emitida electrónicamente; use anulación local.')
    if is_total and NotaCreditoElectronica.objects.filter(factura=factura, tipo_nota='TOTAL').exclude(estado_local__startswith='ELIMINADA').exists():
        raise ValidationError('Ya existe una nota crédito total para esta factura.')

    preview = build_credit_preview(factura, lines)
    if is_total:
        total_facturado, total_creditado = _factura_credit_totals(factura)
        if total_creditado > 0:
            raise ValidationError('No se puede emitir total después de acreditaciones parciales previas.')
        if sum((_to_decimal(l['cantidad_a_acreditar']) for l in lines), Decimal('0')) != total_facturado:
            raise ValidationError('La nota total debe incluir la cantidad completa facturada.')

    payload = _map_payload_for_factus(factura, motivo, lines, is_total=is_total)
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
                precio_unitario=detalle.precio_unitario,
                descuento=Decimal('0'),
                base_impuesto=_to_decimal(line['base_impuesto']),
                impuesto=_to_decimal(line['impuesto']),
                total_linea=_to_decimal(line['total_linea']),
                afecta_inventario=line['afecta_inventario'],
                motivo_linea=line['motivo_linea'],
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
        nota.estado_local = 'ACEPTADA' if nota.estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'} else 'ENVIADA_A_FACTUS'
        nota.response_json = response
        nota.save()
    except Exception as exc:
        nota.estado_local = 'ERROR_INTEGRACION'
        nota.mensaje_error = str(exc)
        nota.save(update_fields=['estado_local', 'mensaje_error', 'updated_at'])
        raise

    if nota.estado_local in {'ACEPTADA', 'ENVIADA_A_FACTUS'}:
        if is_total:
            factura.estado_acreditacion = 'CREDITADA_TOTAL'
        else:
            factura.estado_acreditacion = 'CREDITADA_PARCIAL'
        factura.save(update_fields=['estado_acreditacion', 'updated_at'])
        _apply_inventory_return(nota, user)
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
    nota.save(update_fields=['status_raw_factus', 'estado_electronico', 'status', 'response_json', 'estado_local', 'updated_at'])
    return nota
