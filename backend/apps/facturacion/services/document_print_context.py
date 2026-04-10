"""Helpers para construir contexto de impresión (carta/POS) de documentos electrónicos."""

from __future__ import annotations

from typing import Any

from apps.facturacion.models import FacturaElectronica, RangoNumeracionDIAN


def _fmt_human_date(value: Any) -> str:
    if value is None:
        return '-'
    if hasattr(value, 'strftime'):
        return value.strftime('%d-%m-%Y')
    return str(value).strip() or '-'


def _fmt_date(value: Any) -> str:
    if value is None:
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value).strip()


def _find_matching_range(factura: FacturaElectronica) -> RangoNumeracionDIAN | None:
    range_id = factura.factus_numbering_range_id
    if range_id:
        by_id = (
            RangoNumeracionDIAN.objects.filter(factus_range_id=range_id)
            .order_by('-created_at')
            .first()
        )
        if by_id:
            return by_id

    prefijo = str(factura.factus_number_prefix or '').strip()
    resolucion = str(factura.factus_resolution_number or '').strip()
    if prefijo and resolucion:
        return (
            RangoNumeracionDIAN.objects.filter(prefijo=prefijo, resolucion=resolucion)
            .order_by('-created_at')
            .first()
        )
    return None


def build_document_print_context(
    factura: FacturaElectronica | None,
    *,
    pending_range: RangoNumeracionDIAN | None = None,
) -> dict[str, Any]:
    """Construye un único contexto de presentación para carta/POS.

    Prioridad:
    1) Snapshot persistido en el documento emitido.
    2) Rango local asociado/similar.
    3) Rango pendiente opcional (preview antes de emitir).
    """
    if factura is None:
        return {
            'is_emitted': False,
            'emission_status': 'PENDIENTE',
            'numero_documento': '',
            'reference_code': '',
            'cufe_cude': '',
            'prefijo': '',
            'resolucion': '',
            'rango_desde': None,
            'rango_hasta': None,
            'vigencia_desde': '',
            'vigencia_hasta': '',
            'tipo_rango': 'PENDIENTE',
            'tipo_rango_label': 'Pendiente de emisión',
            'resolucion_lines': ['Resolución de Facturación Electrónica: pendiente por emisión.'],
            'resolucion_texto': 'Resolución de Facturación Electrónica: pendiente por emisión.',
        }

    emitted = bool(str(factura.number or '').strip())
    range_obj = _find_matching_range(factura)
    if not range_obj and pending_range:
        range_obj = pending_range

    resolucion = str(factura.factus_resolution_number or factura.factus_resolution_text or '').strip()
    prefijo = str(factura.factus_number_prefix or '').strip()
    rango_desde = factura.factus_authorized_from
    rango_hasta = factura.factus_authorized_to
    vigencia_desde = _fmt_date(factura.factus_resolution_start_date)
    vigencia_hasta = _fmt_date(factura.factus_resolution_end_date)

    if range_obj:
        resolucion = resolucion or str(range_obj.resolucion or '').strip()
        prefijo = prefijo or str(range_obj.prefijo or '').strip()
        rango_desde = rango_desde if rango_desde is not None else range_obj.desde
        rango_hasta = rango_hasta if rango_hasta is not None else range_obj.hasta
        vigencia_desde = vigencia_desde or _fmt_date(range_obj.fecha_autorizacion)
        vigencia_hasta = vigencia_hasta or _fmt_date(range_obj.fecha_expiracion)

    if range_obj and range_obj.factus_range_id:
        tipo_rango = 'AUTORIZADO_FACTUS'
        tipo_rango_label = 'Rango autorizado sincronizado'
    elif range_obj:
        tipo_rango = 'MANUAL_LOCAL'
        tipo_rango_label = 'Rango manual local'
    else:
        tipo_rango = 'PENDIENTE'
        tipo_rango_label = 'Pendiente de emisión'

    emission_status = str(factura.estado_electronico or factura.status or '').strip() or 'PENDIENTE_REINTENTO'
    resolucion_human = (
        f'Resolución de Facturación Electrónica No: {resolucion or "-"}'
        f' - Prefijo: {prefijo or "-"}'
        f' Rango {rango_desde if rango_desde is not None else "-"} Al {rango_hasta if rango_hasta is not None else "-"}'
        f' - Vigencia desde {_fmt_human_date(vigencia_desde or factura.factus_resolution_start_date)}'
        f' - hasta {_fmt_human_date(vigencia_hasta or factura.factus_resolution_end_date)}'
    )
    lines = [resolucion_human]

    return {
        'is_emitted': emitted,
        'emission_status': emission_status,
        'numero_documento': str(factura.number or '').strip(),
        'reference_code': str(factura.reference_code or '').strip(),
        'cufe_cude': str(factura.cufe or '').strip(),
        'prefijo': prefijo,
        'resolucion': resolucion,
        'rango_desde': rango_desde,
        'rango_hasta': rango_hasta,
        'vigencia_desde': vigencia_desde,
        'vigencia_hasta': vigencia_hasta,
        'tipo_rango': tipo_rango,
        'tipo_rango_label': tipo_rango_label,
        'resolucion_lines': lines,
        'resolucion_texto': ' · '.join(lines),
    }
