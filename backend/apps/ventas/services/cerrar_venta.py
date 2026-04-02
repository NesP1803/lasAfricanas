from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError


def request_user_label(user):
    if not user:
        return ''
    full_name = user.get_full_name().strip()
    return full_name or user.username


def validar_detalles_venta(venta):
    detalles = list(venta.detalles.select_related('producto'))
    if not detalles:
        raise ValidationError('La venta no tiene detalles para facturar.')

    subtotal = sum((detalle.subtotal for detalle in detalles), Decimal('0.00'))
    total_detalles = sum((detalle.total for detalle in detalles), Decimal('0.00'))
    descuento_global = Decimal(venta.descuento_valor or 0)
    total_esperado = total_detalles - descuento_global
    if total_esperado < 0:
        total_esperado = Decimal('0.00')

    normalized_subtotal = Decimal(subtotal).quantize(Decimal('0.01'))
    normalized_iva = Decimal(total_detalles - subtotal).quantize(Decimal('0.01'))
    normalized_total = Decimal(total_esperado).quantize(Decimal('0.01'))

    if normalized_subtotal != Decimal(venta.subtotal).quantize(Decimal('0.01')):
        raise ValidationError('El subtotal no coincide con los detalles.')

    if normalized_iva != Decimal(venta.iva).quantize(Decimal('0.01')):
        raise ValidationError('El IVA no coincide con los detalles.')

    if normalized_total != Decimal(venta.total).quantize(Decimal('0.01')):
        raise ValidationError('El total no coincide con los detalles.')

    return detalles


def registrar_salida_inventario(venta, user, detalles=None):
    if not venta.afecta_inventario:
        return
    if venta.inventario_ya_afectado:
        return

    from apps.inventario.models import MovimientoInventario, Producto

    detalles = detalles or list(venta.detalles.select_related('producto'))
    productos_ids = [detalle.producto_id for detalle in detalles if detalle.afecto_inventario]
    productos = {
        producto.id: producto
        for producto in Producto.objects.select_for_update().filter(id__in=productos_ids)
    } if productos_ids else {}

    movimientos_creados = 0
    for detalle in detalles:
        if not detalle.afecto_inventario:
            continue
        producto = productos.get(detalle.producto_id) or detalle.producto
        stock_anterior = producto.stock
        stock_nuevo = stock_anterior - detalle.cantidad
        observaciones = 'Facturación en caja'
        if stock_nuevo < 0:
            observaciones = (
                f'Facturación en caja con stock negativo permitido '
                f'({stock_anterior} -> {stock_nuevo})'
            )
        MovimientoInventario.objects.create(
            producto=producto,
            tipo='SALIDA',
            cantidad=-abs(detalle.cantidad),
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo,
            costo_unitario=detalle.precio_unitario,
            usuario=user,
            referencia=venta.numero_comprobante or f'VENTA-{venta.id}',
            observaciones=observaciones,
        )
        movimientos_creados += 1

    if movimientos_creados > 0:
        venta.inventario_ya_afectado = True
        venta.save(update_fields=['inventario_ya_afectado', 'updated_at'])


def cerrar_venta_local(venta, user):
    if venta.estado in {'COBRADA', 'FACTURADA'}:
        raise ValidationError('La venta ya está cobrada.')
    if venta.estado not in {'BORRADOR', 'ENVIADA_A_CAJA'}:
        raise ValidationError('La venta no se puede facturar en este estado.')

    detalles = validar_detalles_venta(venta)

    venta.estado = 'COBRADA'
    venta.facturada_por = user
    venta.facturada_at = timezone.now()
    venta.save()

    registrar_salida_inventario(venta, user, detalles=detalles)


def validar_para_facturar_en_caja(venta):
    if venta.estado != 'ENVIADA_A_CAJA':
        raise ValidationError('La venta no está enviada a caja.')

    if venta.tipo_comprobante != 'FACTURA':
        raise ValidationError('Solo las facturas enviadas a caja se pueden facturar en caja.')

    if not venta.enviada_a_caja_at or not venta.enviada_a_caja_por_id:
        raise ValidationError('La venta no tiene traza válida de envío a caja.')

    validar_detalles_venta(venta)


def build_pos_ticket_payload(venta, factura):
    final_fields = factura.response_json.get('final_fields', {}) if isinstance(factura.response_json, dict) else {}
    detalles = []
    discriminacion_iva: dict[Decimal, dict[str, float]] = {}
    for detalle in venta.detalles.select_related('producto').all():
        subtotal_linea = Decimal(detalle.subtotal or 0)
        total_linea = Decimal(detalle.total or 0)
        iva_linea = total_linea - subtotal_linea
        tarifa = Decimal(detalle.iva_porcentaje or 0)
        item_discriminacion = discriminacion_iva.get(tarifa, {'valor_compra': 0.0, 'base_imp': 0.0, 'valor_iva': 0.0})
        item_discriminacion['valor_compra'] += float(total_linea)
        item_discriminacion['base_imp'] += float(subtotal_linea)
        item_discriminacion['valor_iva'] += float(iva_linea)
        discriminacion_iva[tarifa] = item_discriminacion
        detalles.append(
            {
                'descripcion': detalle.producto.nombre,
                'codigo': detalle.producto.codigo,
                'cantidad': float(detalle.cantidad),
                'precio_unitario': float(detalle.precio_unitario),
                'descuento': float(detalle.descuento_unitario),
                'subtotal': float(subtotal_linea),
                'iva_porcentaje': float(detalle.iva_porcentaje),
                'iva_valor': float(iva_linea),
                'total': float(detalle.total),
            }
        )
    return {
        'empresa': {
            'nombre': 'MOTOREPUESTOS LAS AFRICANAS',
        },
        'venta_id': venta.id,
        'numero_factura': factura.number,
        'fecha_hora': venta.facturada_at.isoformat() if venta.facturada_at else venta.fecha.isoformat(),
        'cliente': {
            'nombre': venta.cliente.nombre,
            'documento': venta.cliente.numero_documento,
        },
        'vendedor_caja': request_user_label(venta.facturada_por),
        'medio_pago': venta.get_medio_pago_display(),
        'estado_documento': factura.status,
        'reference_code': factura.reference_code,
        'subtotal': float(venta.subtotal),
        'impuestos': float(venta.iva),
        'descuento': float(venta.descuento_valor),
        'total': float(venta.total),
        'cufe': factura.cufe,
        'uuid': factura.uuid,
        'qr_url': (final_fields.get('qr_url') or final_fields.get('public_url') or factura.qr.url) if factura.qr else (
            final_fields.get('qr_url') or final_fields.get('public_url') or final_fields.get('qr', '')
        ),
        'factus_qr': final_fields.get('qr', ''),
        'qr_image': final_fields.get('qr_image', ''),
        'xml_url': factura.xml_url,
        'discriminacion_iva': [
            {
                'tarifa': float(tarifa),
                'valor_compra': valores['valor_compra'],
                'base_imp': valores['base_imp'],
                'valor_iva': valores['valor_iva'],
            }
            for tarifa, valores in sorted(discriminacion_iva.items(), key=lambda item: item[0])
        ],
        'items': detalles,
    }


def build_factura_ready_payload(venta, factura):
    final_fields = factura.response_json.get('final_fields', {}) if isinstance(factura.response_json, dict) else {}
    bill_errors = factura.response_json.get('bill_errors', []) if isinstance(factura.response_json, dict) else []
    return {
        'id': factura.id,
        'number': factura.number,
        'numero_visible': factura.number,
        'prefix': ''.join(filter(str.isalpha, factura.number or '')),
        'status': factura.status,
        'estado': factura.status,
        'cufe': factura.cufe,
        'uuid': factura.uuid,
        'qr_url': factura.qr.url if factura.qr else '',
        'qr_image': final_fields.get('qr_image', ''),
        'factus_qr': final_fields.get('qr', ''),
        'public_url': final_fields.get('public_url', ''),
        'bill_errors': bill_errors if isinstance(bill_errors, list) else [],
        'observaciones': factura.mensaje_error or '',
        'reference_code': factura.reference_code,
        'xml_url': factura.xml_url,
        'pdf_url': factura.pdf_url,
        'xml_local_path': factura.xml_local_path,
        'pdf_local_path': factura.pdf_local_path,
        'cliente': {
            'nombre': venta.cliente.nombre,
            'documento': venta.cliente.numero_documento,
            'email': venta.cliente.email,
            'telefono': venta.cliente.telefono,
            'direccion': venta.cliente.direccion,
        },
        'totales': {
            'subtotal': float(venta.subtotal),
            'impuestos': float(venta.iva),
            'descuento': float(venta.descuento_valor),
            'total': float(venta.total),
            'efectivo_recibido': float(venta.efectivo_recibido),
            'cambio': float(venta.cambio),
        },
    }


def estado_electronico_ui(factura):
    if factura.status == 'ACEPTADA' and factura.codigo_error == 'OBSERVACIONES_FACTUS':
        return 'EMITIDA_CON_OBSERVACIONES'
    return factura.status
