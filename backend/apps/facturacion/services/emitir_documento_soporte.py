"""Servicio de emisión de documento soporte electrónico vía Factus."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.facturacion.models import DocumentoSoporteElectronico
from apps.facturacion.services.facturar_venta import map_factus_status
from apps.facturacion.services.factus_client import FactusAPIError, FactusClient, FactusValidationError
from apps.facturacion.services.support_document_payload_builder import build_support_document_payload
from apps.inventario.models import MovimientoInventario, Producto, Proveedor


def _extract_support_document_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    support_document = data.get('support_document', data)
    return {
        'cufe': str(support_document.get('cufe', '')).strip(),
        'uuid': str(support_document.get('uuid', '')).strip(),
        'number': str(support_document.get('number', '')).strip(),
        'xml_url': str(support_document.get('xml_url', '')).strip(),
        'pdf_url': str(support_document.get('pdf_url', '')).strip(),
        'status': map_factus_status(response_json)[0],
    }


def _afectar_inventario_desde_documento_soporte(
    *,
    payload_data: dict[str, Any],
    documento: DocumentoSoporteElectronico,
    user=None,
) -> None:
    items = payload_data.get('items') if isinstance(payload_data.get('items'), list) else []
    if not items:
        return
    for item in items:
        cantidad = Decimal(str(item.get('cantidad') or '0'))
        if cantidad <= 0:
            continue
        producto_id = item.get('producto_id')
        producto = Producto.objects.filter(pk=producto_id, is_active=True).first() if producto_id else None
        costo_unitario = Decimal(str(item.get('precio') or (producto.precio_costo if producto else '0') or '0'))
        if producto is None:
            codigo = str(item.get('codigo_referencia') or '').strip()
            nombre = str(item.get('descripcion') or '').strip()
            categoria_id = item.get('categoria_id')
            if not codigo or not nombre or not categoria_id:
                continue
            proveedor = None
            if payload_data.get('proveedor_id'):
                proveedor = Proveedor.objects.filter(pk=payload_data.get('proveedor_id'), is_active=True).first()
            iva_porcentaje = Decimal(str(item.get('iva_porcentaje') or '0'))
            precio_venta = costo_unitario + (costo_unitario * iva_porcentaje / Decimal('100'))
            producto = Producto.objects.filter(codigo=codigo).first()
            if producto is None:
                producto = Producto.objects.create(
                    codigo=codigo,
                    nombre=nombre,
                    categoria_id=int(categoria_id),
                    proveedor=proveedor,
                    precio_costo=costo_unitario,
                    precio_venta=precio_venta,
                    precio_venta_minimo=precio_venta,
                    stock=Decimal('0'),
                    stock_minimo=Decimal('1'),
                    unidad_medida=str(item.get('unidad_medida') or 'N/A')[:20] or 'N/A',
                    iva_porcentaje=iva_porcentaje,
                    iva_exento=iva_porcentaje == Decimal('0'),
                )
        stock_anterior = Decimal(str(producto.stock or '0'))
        stock_nuevo = stock_anterior + cantidad
        producto.stock = stock_nuevo
        producto.precio_costo = costo_unitario
        producto.save(update_fields=['stock', 'precio_costo', 'ultima_compra', 'updated_at'])
        if user is not None:
            MovimientoInventario.objects.create(
                producto=producto,
                tipo='ENTRADA',
                cantidad=cantidad,
                stock_anterior=stock_anterior,
                stock_nuevo=stock_nuevo,
                costo_unitario=costo_unitario,
                usuario=user,
                referencia=f'DOC-SOP-{documento.number}',
                observaciones='Entrada por emisión de documento soporte.',
            )


def emitir_documento_soporte(data: dict[str, Any], *, user=None) -> DocumentoSoporteElectronico:
    payload_data = dict(data)
    proveedor_id = payload_data.get('proveedor_id')
    if proveedor_id:
        proveedor = Proveedor.objects.filter(pk=proveedor_id, is_active=True).first()
        if proveedor:
            payload_data.setdefault('proveedor_nombre', proveedor.nombre)
            payload_data.setdefault('proveedor_documento', proveedor.nit)
            payload_data.setdefault('proveedor_tipo_documento', 'NIT' if str(proveedor.nit or '').strip() else 'CC')
            payload_data.setdefault('provider_address', proveedor.direccion)
            payload_data.setdefault('provider_email', proveedor.email)
            payload_data.setdefault('provider_phone', proveedor.telefono)
            payload_data.setdefault('provider_city', proveedor.ciudad)

    payload = build_support_document_payload(payload_data)
    try:
        response_json = FactusClient().create_and_validate_support_document(payload)
    except FactusAPIError as exc:
        if exc.status_code == 422:
            raise FactusValidationError(f'Factus rechazó el documento soporte por validación: {exc.provider_detail}') from exc
        raise
    fields = _extract_support_document_data(response_json)

    with transaction.atomic():
        documento = DocumentoSoporteElectronico.objects.create(
            number=fields['number'] or str(payload_data.get('number', 'DS-PENDIENTE')).strip(),
            proveedor_nombre=str(payload_data.get('proveedor_nombre', '')).strip(),
            proveedor_documento=str(payload_data.get('proveedor_documento', '')).strip(),
            proveedor_tipo_documento=str(payload_data.get('proveedor_tipo_documento', '')).strip(),
            cufe=fields['cufe'] or None,
            uuid=fields['uuid'] or None,
            status=fields['status'],
            xml_url=fields['xml_url'] or None,
            pdf_url=fields['pdf_url'] or None,
            response_json=response_json,
        )
        _afectar_inventario_desde_documento_soporte(payload_data=payload_data, documento=documento, user=user)
    return documento
