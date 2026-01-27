from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

from apps.core.models import ConfiguracionEmpresa, ConfiguracionFacturacion
from apps.ventas.models import Venta, DetalleVenta

from ..models import DocumentType


def _money(value: Optional[Decimal]) -> str:
    if value is None:
        return "0.00"
    return f"{value:.2f}"


def _empresa_context() -> Dict[str, Any]:
    empresa = ConfiguracionEmpresa.objects.first()
    facturacion = ConfiguracionFacturacion.objects.first()
    if empresa:
        return {
            "nombre": empresa.razon_social,
            "nit": f"{empresa.identificacion}{('-' + empresa.dv) if empresa.dv else ''}",
            "direccion": empresa.direccion,
            "ciudad": empresa.ciudad or empresa.municipio,
            "telefono": empresa.telefono,
            "regimen": empresa.regimen,
            "resolucion": facturacion.resolucion if facturacion else "",
            "rango": "",
        }
    return {
        "nombre": "LAS AFRICANAS",
        "nit": "900000000-0",
        "direccion": "Dirección principal",
        "ciudad": "Santa Marta",
        "telefono": "0000000",
        "regimen": "RÉGIMEN COMÚN",
        "resolucion": "",
        "rango": "",
    }


def _venta_items(detalles: List[DetalleVenta]) -> List[Dict[str, Any]]:
    items = []
    for detalle in detalles:
        items.append(
            {
                "descripcion": detalle.producto_nombre or "",
                "codigo": detalle.producto_codigo or "",
                "cantidad": detalle.cantidad,
                "valor_unitario": _money(detalle.precio_unitario),
                "descuento": _money(detalle.descuento_unitario),
                "iva_pct": _money(detalle.iva_porcentaje),
                "total": _money(detalle.total),
            }
        )
    return items


def _venta_context(venta: Venta) -> Dict[str, Any]:
    empresa = _empresa_context()
    cliente = {
        "nombre": venta.cliente.nombre,
        "nit": venta.cliente.numero_documento,
        "direccion": venta.cliente.direccion,
        "telefono": venta.cliente.telefono,
    }
    detalles = list(venta.detalles.all())
    items = _venta_items(detalles)
    totales = {
        "subtotal": _money(venta.subtotal),
        "impuestos": _money(venta.iva),
        "descuentos": _money(venta.descuento_valor),
        "total": _money(venta.total),
        "recibido": _money(venta.efectivo_recibido),
        "cambio": _money(venta.cambio),
    }
    doc = {
        "tipo": venta.get_tipo_comprobante_display().upper(),
        "numero": venta.numero_comprobante,
        "fecha": venta.fecha.strftime("%Y-%m-%d"),
        "hora": venta.fecha.strftime("%H:%M"),
        "estado": venta.get_estado_display(),
        "medio_pago": venta.get_medio_pago_display(),
        "observaciones": venta.observaciones or "",
    }
    return {
        "empresa": empresa,
        "doc": doc,
        "cliente": cliente,
        "items": items,
        "totales": totales,
        "extras": {},
    }


def _mock_context(doc_type: str) -> Dict[str, Any]:
    now = timezone.localtime()
    return {
        "empresa": _empresa_context(),
        "doc": {
            "tipo": doc_type,
            "numero": "000001",
            "fecha": now.strftime("%Y-%m-%d"),
            "hora": now.strftime("%H:%M"),
            "estado": "CONFIRMADA",
            "medio_pago": "EFECTIVO",
            "observaciones": "Documento de muestra para previsualización.",
        },
        "cliente": {
            "nombre": "Cliente de ejemplo",
            "nit": "123456789",
            "direccion": "Calle 123",
            "telefono": "3000000000",
        },
        "items": [
            {
                "descripcion": "Producto de prueba",
                "codigo": "PRD-001",
                "cantidad": 2,
                "valor_unitario": "15000.00",
                "descuento": "0.00",
                "iva_pct": "19.00",
                "total": "30000.00",
            },
            {
                "descripcion": "Servicio adicional",
                "codigo": "SRV-010",
                "cantidad": 1,
                "valor_unitario": "20000.00",
                "descuento": "0.00",
                "iva_pct": "0.00",
                "total": "20000.00",
            },
        ],
        "totales": {
            "subtotal": "50000.00",
            "impuestos": "5700.00",
            "descuentos": "0.00",
            "total": "55700.00",
            "recibido": "60000.00",
            "cambio": "4300.00",
        },
        "extras": {
            "mensaje": "Gracias por su compra",
        },
    }


def build_document_context(
    document_type: str,
    document_id: Optional[int] = None,
) -> Dict[str, Any]:
    if document_type in [
        DocumentType.QUOTATION,
        DocumentType.INVOICE,
        DocumentType.DELIVERY_NOTE,
    ]:
        venta_type = {
            DocumentType.QUOTATION: 'COTIZACION',
            DocumentType.INVOICE: 'FACTURA',
            DocumentType.DELIVERY_NOTE: 'REMISION',
        }[document_type]
        if document_id:
            venta = (
                Venta.objects.select_related('cliente')
                .prefetch_related('detalles')
                .filter(id=document_id, tipo_comprobante=venta_type)
                .first()
            )
            if venta:
                return _venta_context(venta)
        return _mock_context(venta_type)
    return _mock_context(document_type)
