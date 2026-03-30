from __future__ import annotations

import logging
import time as time_module

from rest_framework.exceptions import ValidationError

from apps.facturacion.services import FactusAPIError, FactusAuthError, emitir_nota_credito
from apps.ventas.models import RemisionAnulada, VentaAnulada

logger = logging.getLogger(__name__)


def validar_estado_para_anulacion(venta):
    if venta.estado == 'ANULADA':
        raise ValidationError('Esta venta ya está anulada.')
    if venta.estado in {'COBRADA', 'FACTURADA'} and venta.tipo_comprobante == 'FACTURA' and venta.facturada_at is None:
        raise ValidationError('La venta está en un estado inconsistente y no se puede anular.')


def build_credit_note_items(venta):
    items = []
    for detalle in venta.detalles.select_related('producto').all():
        items.append(
            {
                'code_reference': detalle.producto.codigo,
                'name': detalle.producto.nombre,
                'quantity': float(detalle.cantidad),
                'price': float(detalle.precio_unitario),
                'tax_rate': float(detalle.iva_porcentaje),
                'discount_rate': 0,
            }
        )
    return items


def anular_factura_electronica_con_nota_credito(venta, motivo, *, max_reintentos=2, backoff_segundos=0.3):
    if not hasattr(venta, 'factura_electronica_factus'):
        return None

    factura = venta.factura_electronica_factus
    if factura.status != 'ACEPTADA':
        return None

    items = build_credit_note_items(venta)
    ultimo_error = None
    for intento in range(max_reintentos + 1):
        try:
            nota_credito = emitir_nota_credito(factura_id=factura.id, motivo=motivo, items=items)
            if nota_credito.status != 'ACEPTADA':
                raise FactusAPIError(
                    f'La nota crédito no fue aceptada por Factus (estado={nota_credito.status}).'
                )
            return nota_credito
        except (FactusAPIError, FactusAuthError) as exc:
            ultimo_error = exc
            logger.warning(
                'Reintento nota crédito para venta_id=%s intento=%s/%s error=%s',
                venta.id,
                intento + 1,
                max_reintentos + 1,
                str(exc),
            )
            if intento >= max_reintentos:
                break
            time_module.sleep(backoff_segundos * (intento + 1))

    if ultimo_error:
        raise ultimo_error
    return None


def debe_revertir_inventario(venta):
    if not venta.afecta_inventario:
        return False
    if venta.inventario_ya_afectado:
        return True

    from apps.inventario.models import MovimientoInventario

    referencias = {f'VENTA-{venta.id}'}
    if venta.numero_comprobante:
        referencias.add(venta.numero_comprobante)
    return MovimientoInventario.objects.filter(
        tipo='SALIDA',
        referencia__in=referencias,
    ).exists()


def revertir_inventario_venta_anulada(venta, user, descripcion=''):
    from apps.inventario.models import MovimientoInventario, Producto

    detalles = [detalle for detalle in venta.detalles.all() if detalle.afecto_inventario]
    productos_ids = [detalle.producto_id for detalle in detalles]
    productos = {
        producto.id: producto
        for producto in Producto.objects.select_for_update().filter(id__in=productos_ids)
    }

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


def anular_venta(venta, user, *, motivo, descripcion='', devuelve_inventario=True):
    validar_estado_para_anulacion(venta)

    nota_credito = anular_factura_electronica_con_nota_credito(venta, motivo)

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

    venta.estado = 'ANULADA'
    venta.save(update_fields=['estado', 'updated_at'])

    if devuelve_inventario and debe_revertir_inventario(venta):
        revertir_inventario_venta_anulada(venta, user, descripcion=descripcion)

    return nota_credito
