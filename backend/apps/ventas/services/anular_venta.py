from __future__ import annotations

from rest_framework.exceptions import ValidationError

from apps.facturacion.services.credit_note_workflow import create_credit_note
from apps.ventas.models import RemisionAnulada, VentaAnulada


def validar_estado_para_anulacion(venta):
    if venta.estado == 'ANULADA':
        raise ValidationError('Esta venta ya está anulada.')


def debe_revertir_inventario(venta):
    if not venta.afecta_inventario:
        return False
    if venta.inventario_ya_afectado:
        return True

    from apps.inventario.models import MovimientoInventario

    referencias = {f'VENTA-{venta.id}'}
    if venta.numero_comprobante:
        referencias.add(venta.numero_comprobante)
    return MovimientoInventario.objects.filter(tipo='SALIDA', referencia__in=referencias).exists()


def revertir_inventario_venta_anulada(venta, user, descripcion=''):
    from apps.inventario.models import MovimientoInventario, Producto

    detalles = [detalle for detalle in venta.detalles.all() if detalle.afecto_inventario]
    productos = {p.id: p for p in Producto.objects.select_for_update().filter(id__in=[d.producto_id for d in detalles])}
    for detalle in detalles:
        producto = productos.get(detalle.producto_id) or detalle.producto
        stock_anterior = producto.stock
        stock_nuevo = stock_anterior + detalle.cantidad
        MovimientoInventario.objects.create(
            producto=producto,
            tipo='DEVOLUCION',
            cantidad=detalle.cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo,
            costo_unitario=detalle.precio_unitario,
            usuario=user,
            referencia=f'Anulación {venta.numero_comprobante}',
            observaciones=f'Devolución por anulación: {descripcion}',
        )
        producto.stock = stock_nuevo
        producto.save(update_fields=['stock', 'updated_at'])


def _registrar_anulacion_local(venta, user, *, motivo, descripcion, devuelve_inventario):
    if venta.tipo_comprobante == 'REMISION':
        RemisionAnulada.objects.create(
            remision=venta,
            motivo=motivo,
            descripcion=descripcion,
            anulado_por=user,
            devuelve_inventario=devuelve_inventario,
        )
    else:
        VentaAnulada.objects.create(
            venta=venta,
            motivo=motivo,
            descripcion=descripcion,
            anulado_por=user,
            devuelve_inventario=devuelve_inventario,
        )


def anular_venta(venta, user, *, motivo, descripcion='', devuelve_inventario=True):
    validar_estado_para_anulacion(venta)
    factura_emitida = getattr(venta, 'factura_electronica_factus', None)

    # Remisión convertida a factura: se anula sobre la factura asociada
    if venta.tipo_comprobante == 'REMISION' and venta.facturas_generadas.exists():
        factura_generada = venta.facturas_generadas.order_by('-id').first()
        if factura_generada:
            return anular_venta(factura_generada, user, motivo=motivo, descripcion=descripcion, devuelve_inventario=devuelve_inventario)

    if factura_emitida and factura_emitida.emitida_en_factus and (factura_emitida.estado_electronico or factura_emitida.status) in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
        lines = [
            {
                'detalle_venta_original_id': detalle.id,
                'cantidad_a_acreditar': detalle.cantidad,
                'afecta_inventario': devuelve_inventario and detalle.afecto_inventario,
                'motivo_linea': descripcion or motivo,
            }
            for detalle in venta.detalles.all()
        ]
        nota, meta = create_credit_note(factura=factura_emitida, motivo=motivo, lines=lines, is_total=True, user=user)
        if meta.get('result') == 'accepted':
            _registrar_anulacion_local(venta, user, motivo=motivo, descripcion=descripcion, devuelve_inventario=devuelve_inventario)
            venta.refresh_from_db()
        return {'nota_credito': nota, 'flow_meta': meta}

    # Remisión no electrónica o factura local
    _registrar_anulacion_local(venta, user, motivo=motivo, descripcion=descripcion, devuelve_inventario=devuelve_inventario)
    venta.estado = 'ANULADA'
    venta.save(update_fields=['estado', 'updated_at'])
    if devuelve_inventario and debe_revertir_inventario(venta):
        revertir_inventario_venta_anulada(venta, user, descripcion=descripcion)
    return {'nota_credito': None, 'flow_meta': {'ok': True, 'result': 'accepted', 'finalized': True, 'business_effects_applied': True}}
