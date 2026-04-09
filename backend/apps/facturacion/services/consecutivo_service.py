"""Resolución de rangos DIAN oficiales sincronizados desde Factus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.models import ConfiguracionFacturacion
from apps.facturacion.constants import (
    LOCAL_TO_FACTUS_CODE,
    document_matches_local_code,
    normalize_local_document_code,
)
from apps.facturacion.models import ConfiguracionDIAN, FactusNumberingRange
from apps.facturacion.services.factus_client import FactusClient, FactusValidationError
from apps.facturacion.services.factus_environment import resolve_factus_environment

logger = logging.getLogger(__name__)


@dataclass
class InvoiceSequence:
    number: str
    numbering_range_id: int | None


@dataclass
class TechnicalRange:
    factus_id: int
    document_code: str
    factus_document_code: str
    prefix: str
    from_number: int | None
    to_number: int | None
    current_number: int | None
    is_active: bool
    is_expired: bool
    is_associated_to_software: bool
    start_date: date | None
    end_date: date | None
    resolution_number: str
    environment: str
    raw: dict[str, Any]


DOCUMENT_CONFIG_MAP: dict[str, dict[str, str]] = {
    'FACTURA_VENTA': {
        'id_field': 'factus_numbering_range_id_factura_venta',
        'meta_prefix': 'factus_factura_venta',
    },
    'NOTA_CREDITO': {
        'id_field': 'factus_numbering_range_id_nota_credito',
        'meta_prefix': 'factus_nota_credito',
    },
    'NOTA_DEBITO': {
        'id_field': 'factus_numbering_range_id_nota_debito',
        'meta_prefix': 'factus_nota_debito',
    },
    'DOCUMENTO_SOPORTE': {
        'id_field': 'factus_numbering_range_id_documento_soporte',
        'meta_prefix': 'factus_documento_soporte',
    },
    'NOTA_AJUSTE_DOCUMENTO_SOPORTE': {
        'id_field': 'factus_numbering_range_id_nota_ajuste_documento_soporte',
        'meta_prefix': 'factus_nota_ajuste_documento_soporte',
    },
}


def _extract_ranges_list(payload: Any) -> list[dict[str, Any]]:
    data = payload.get('data', payload) if isinstance(payload, dict) else payload
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        nested = data.get('data', data.get('numbering_ranges', []))
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).split('T')[0].strip())
    except Exception:
        return None


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 'yes', 'si', 'sí', 'on', 'active', 'activo'}:
        return True
    if normalized in {'0', 'false', 'no', 'off', 'inactive', 'inactivo'}:
        return False
    return default


def _normalize_environment(value: Any, *, fallback: str) -> str:
    normalized = str(value or '').strip().upper()
    if not normalized:
        return fallback
    if normalized in {'PROD', 'PRODUCTION', '2'}:
        return 'PRODUCTION'
    if normalized in {'SANDBOX', 'HABILITACION', 'HABILITACIÓN', 'TEST', '1'}:
        return 'SANDBOX'
    return fallback


def _matches_local_document(local_document_code: str, remote_document_code: str) -> bool:
    return document_matches_local_code(local_document_code, remote_document_code)


def _normalize_technical_range(raw: dict[str, Any], *, environment: str) -> TechnicalRange:
    factus_id = int(raw.get('id') or raw.get('numbering_range_id') or raw.get('range_id') or 0)
    remote_doc = str(raw.get('document') or raw.get('document_code') or raw.get('document_type') or '').strip()
    document_code = normalize_local_document_code(remote_doc, default='') if remote_doc else ''
    end_date = _as_date(raw.get('end_date') or raw.get('valid_to'))
    start_date = _as_date(raw.get('start_date') or raw.get('valid_from'))
    is_expired = _as_bool(raw.get('is_expired'), default=False)
    if end_date and end_date < timezone.now().date():
        is_expired = True
    is_active = _as_bool(raw.get('is_active'), default=True) and not is_expired
    is_associated = _as_bool(raw.get('is_associated_to_software'), default=True)
    range_env = _normalize_environment(raw.get('environment') or raw.get('ambiente'), fallback=environment)

    return TechnicalRange(
        factus_id=factus_id,
        document_code=document_code,
        factus_document_code=str(raw.get('document_code') or raw.get('document') or raw.get('document_type') or '').strip(),
        prefix=str(raw.get('prefix') or '').strip(),
        from_number=int(raw.get('from') or raw.get('from_number') or 0) or None,
        to_number=int(raw.get('to') or raw.get('to_number') or 0) or None,
        current_number=int(raw.get('current') or raw.get('current_number') or raw.get('from') or 0) or None,
        is_active=is_active,
        is_expired=is_expired,
        is_associated_to_software=is_associated,
        start_date=start_date,
        end_date=end_date,
        resolution_number=str(raw.get('resolution_number') or ''),
        environment=range_env,
        raw=raw,
    )


def _range_match_signature(item: TechnicalRange) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        str(item.prefix or '').strip().upper(),
        str(item.resolution_number or '').strip().upper(),
        str(item.from_number or ''),
        str(item.to_number or ''),
        str(item.start_date or ''),
        str(item.end_date or ''),
        str(item.document_code or '').strip().upper(),
        str(item.environment or '').strip().upper(),
    )


def _merge_software_association(
    base_ranges: list[TechnicalRange],
    software_payload: dict[str, Any],
    *,
    environment: str,
) -> list[TechnicalRange]:
    software_ranges_raw = _extract_ranges_list(software_payload)
    if not software_ranges_raw:
        return base_ranges

    software_ranges = [_normalize_technical_range(item, environment=environment) for item in software_ranges_raw]
    by_signature = {_range_match_signature(item): item for item in software_ranges}
    merged: list[TechnicalRange] = []
    for item in base_ranges:
        signature = _range_match_signature(item)
        associated = item.is_associated_to_software
        if signature in by_signature:
            associated = True
        merged.append(
            TechnicalRange(
                factus_id=item.factus_id,
                document_code=item.document_code,
                factus_document_code=item.factus_document_code,
                prefix=item.prefix,
                from_number=item.from_number,
                to_number=item.to_number,
                current_number=item.current_number,
                is_active=item.is_active,
                is_expired=item.is_expired,
                is_associated_to_software=associated,
                start_date=item.start_date,
                end_date=item.end_date,
                resolution_number=item.resolution_number,
                environment=item.environment,
                raw=item.raw,
            )
        )
    return merged


def _get_configured_range_id(configuracion: ConfiguracionFacturacion | None, field_name: str) -> int:
    if not configuracion or not field_name:
        return 0
    return int(getattr(configuracion, field_name, 0) or 0)


def _resolve_config_field(document_code: str) -> str:
    config = DOCUMENT_CONFIG_MAP.get(document_code, {})
    return config.get('id_field', '')


def _metadata_field_names(document_code: str) -> tuple[str, list[str]]:
    config = DOCUMENT_CONFIG_MAP.get(document_code, {})
    meta_prefix = config.get('meta_prefix', '')
    if not meta_prefix:
        return '', []
    fields = [
        f'{meta_prefix}_document_code',
        f'{meta_prefix}_range_name',
        f'{meta_prefix}_range_prefix',
        f'{meta_prefix}_resolution_number',
        f'{meta_prefix}_range_from',
        f'{meta_prefix}_range_to',
        f'{meta_prefix}_valid_from',
        f'{meta_prefix}_valid_to',
        f'{meta_prefix}_environment',
        f'{meta_prefix}_current',
        f'{meta_prefix}_is_valid',
        f'{meta_prefix}_last_sync_at',
    ]
    return meta_prefix, fields


def _fetch_factus_technical_ranges() -> list[TechnicalRange]:
    environment = resolve_factus_environment()
    client = FactusClient()
    logger.info(
        'facturacion.numbering_ranges.fetch.call endpoint=%s params=%s environment=%s',
        client.numbering_ranges_path,
        {'filter[is_active]': 1},
        environment,
    )
    payload = client.get_numbering_ranges()
    ranges = [_normalize_technical_range(raw, environment=environment) for raw in _extract_ranges_list(payload)]
    logger.info(
        'facturacion.numbering_ranges.fetch.call endpoint=%s params=%s environment=%s',
        client.numbering_ranges_dian_path,
        {},
        environment,
    )
    software_payload = client.get_software_numbering_ranges()
    ranges = _merge_software_association(ranges, software_payload, environment=environment)
    software_signatures = {
        _range_match_signature(_normalize_technical_range(item, environment=environment))
        for item in _extract_ranges_list(software_payload)
    }
    logger.info(
        'facturacion.numbering_ranges.fetch.software_signatures count=%s sample=%s',
        len(software_signatures),
        list(software_signatures)[:5],
    )
    logger.info(
        'facturacion.numbering_ranges.fetch environment=%s endpoint=%s total=%s sample_ids=%s',
        environment,
        client.numbering_ranges_path,
        len(ranges),
        [item.factus_id for item in ranges[:5]],
    )
    return ranges


def _pick_valid_range(
    *,
    ranges: list[TechnicalRange],
    document_code: str,
    configured_id: int,
    environment: str,
) -> tuple[int, list[str]]:
    discard_reasons: list[str] = []
    by_document = [
        item for item in ranges
        if (
            (
                _matches_local_document(document_code, item.document_code)
                or _matches_local_document(document_code, item.factus_document_code)
            )
            and item.factus_id > 0
            and item.environment == environment
        )
    ]

    for item in ranges:
        if not (
            _matches_local_document(document_code, item.document_code)
            or _matches_local_document(document_code, item.factus_document_code)
        ):
            discard_reasons.append(
                f'id={item.factus_id}:descartado_documento_incorrecto local={document_code} remote={item.document_code}/{item.factus_document_code}'
            )
        elif item.environment != environment:
            discard_reasons.append(f'id={item.factus_id}:descartado_ambiente_incorrecto={item.environment}')
        elif item.factus_id <= 0:
            discard_reasons.append(f'id={item.factus_id}:descartado_id_invalido')
        elif not item.is_associated_to_software:
            discard_reasons.append(f'id={item.factus_id}:descartado_no_asociado_software')
        elif item.is_expired:
            discard_reasons.append(f'id={item.factus_id}:descartado_expirado')
        elif not item.is_active:
            discard_reasons.append(f'id={item.factus_id}:descartado_inactivo')

    usable = [item for item in by_document if item.is_associated_to_software and item.is_active]

    if configured_id > 0:
        configured = next((item for item in by_document if item.factus_id == configured_id), None)
        if configured and configured.is_associated_to_software and configured.is_active:
            return configured_id, discard_reasons
        discard_reasons.append(f'id={configured_id}:descartado_configurado_no_vigente')

    if not usable:
        return 0, discard_reasons

    usable.sort(key=lambda item: ((item.end_date or date.max), (item.start_date or date.min)), reverse=True)
    return int(usable[0].factus_id), discard_reasons


def _persist_selected_range_metadata(
    *,
    configuracion: ConfiguracionFacturacion,
    selected: TechnicalRange,
    document_code: str,
    field_name: str,
    environment: str,
) -> None:
    meta_prefix, metadata_fields = _metadata_field_names(document_code)
    if not meta_prefix:
        return
    fields_to_update = [
        field_name,
        'ambiente_factus',
        'prefijo_factura_electronica',
        *metadata_fields,
    ]
    setattr(configuracion, field_name, selected.factus_id)
    configuracion.ambiente_factus = environment
    if document_code == 'FACTURA_VENTA':
        configuracion.prefijo_factura_electronica = selected.prefix or ''
    setattr(configuracion, f'{meta_prefix}_document_code', selected.factus_document_code or LOCAL_TO_FACTUS_CODE.get(document_code, ''))
    setattr(configuracion, f'{meta_prefix}_range_name', str(selected.raw.get('name') or selected.raw.get('description') or '').strip())
    setattr(configuracion, f'{meta_prefix}_range_prefix', selected.prefix or '')
    setattr(configuracion, f'{meta_prefix}_resolution_number', selected.resolution_number or '')
    setattr(configuracion, f'{meta_prefix}_range_from', selected.from_number)
    setattr(configuracion, f'{meta_prefix}_range_to', selected.to_number)
    setattr(configuracion, f'{meta_prefix}_valid_from', selected.start_date)
    setattr(configuracion, f'{meta_prefix}_valid_to', selected.end_date)
    setattr(configuracion, f'{meta_prefix}_environment', selected.environment)
    setattr(configuracion, f'{meta_prefix}_current', selected.current_number)
    setattr(configuracion, f'{meta_prefix}_is_valid', bool(
        selected.factus_id > 0 and selected.is_associated_to_software and selected.is_active
    ))
    setattr(configuracion, f'{meta_prefix}_last_sync_at', timezone.now())
    configuracion.save(update_fields=fields_to_update)
    logger.info(
        'facturacion.numbering_range.resolve.persisted_metadata document_code=%s config_id=%s field=%s range_id=%s prefix=%s doc=%s resolution=%s from=%s to=%s start=%s end=%s env=%s current=%s valid=%s',
        document_code,
        configuracion.pk,
        field_name,
        selected.factus_id,
        selected.prefix,
        getattr(configuracion, f'{meta_prefix}_document_code', ''),
        selected.resolution_number,
        selected.from_number,
        selected.to_number,
        selected.start_date,
        selected.end_date,
        selected.environment,
        selected.current_number,
        getattr(configuracion, f'{meta_prefix}_is_valid', False),
    )


def resolve_numbering_range(document_code: str = 'FACTURA_VENTA') -> FactusNumberingRange:
    today = timezone.now().date()

    if not FactusNumberingRange.objects.exists():
        raise FactusValidationError(
            'No hay rangos técnicos disponibles en la caché local de Factus para este documento.'
        )

    rango = (
        FactusNumberingRange.objects.filter(
            document=document_code,
            is_active=True,
            end_date__gte=today,
        )
        .order_by('start_date')
        .first()
    )
    if not rango:
        raise FactusValidationError(
            'No hay rangos técnicos vigentes disponibles en Factus para este documento.'
        )

    return rango


def resolve_electronic_numbering_range_id(document_code: str = 'FACTURA_VENTA', *, force_refresh: bool = False) -> int:
    """
    Resuelve automáticamente el identificador técnico de rango electrónico.

    Prioridad:
    1) Configuración técnica local si sigue vigente en Factus.
    2) Auto-resolución desde rangos autorizados en Factus.
    3) Persistencia automática del id válido encontrado.
    """
    configuracion = ConfiguracionFacturacion.objects.order_by('-id').first()
    field_name = _resolve_config_field(document_code)
    configured_id = _get_configured_range_id(configuracion, field_name)
    environment = resolve_factus_environment()

    logger.info(
        'facturacion.numbering_range.resolve.start document_code=%s environment=%s configured_id=%s config_id=%s config_env=%s',
        document_code,
        environment,
        configured_id,
        getattr(configuracion, 'id', None),
        getattr(configuracion, 'ambiente_factus', None),
    )

    if not field_name:
        raise FactusValidationError(
            f'No se encontró en Factus un rango autorizado y vigente para {document_code} en el ambiente actual.'
        )

    ranges = _fetch_factus_technical_ranges()
    for item in ranges:
        logger.info(
            'facturacion.numbering_range.resolve.range_summary id=%s prefix=%s document=%s/%s resolution=%s start_date=%s end_date=%s from=%s to=%s current=%s active=%s expired=%s environment=%s associated_to_software=%s',
            item.factus_id,
            item.prefix,
            item.document_code,
            item.factus_document_code,
            item.resolution_number,
            item.start_date,
            item.end_date,
            item.from_number,
            item.to_number,
            item.current_number,
            item.is_active,
            item.is_expired,
            item.environment,
            item.is_associated_to_software,
        )
    selected_id, discard_reasons = _pick_valid_range(
        ranges=ranges,
        document_code=document_code,
        configured_id=configured_id,
        environment=environment,
    )

    logger.info(
        'facturacion.numbering_range.resolve.candidates document_code=%s environment=%s total=%s selected_id=%s discard_reasons=%s',
        document_code,
        environment,
        len(ranges),
        selected_id,
        discard_reasons[:20],
    )

    if selected_id <= 0:
        dian_config = ConfiguracionDIAN.objects.order_by('-id').first()
        logger.error(
            'facturacion.numbering_range.resolve.diagnostic_not_found document_code=%s environment=%s configured_id=%s config_id=%s config_env=%s software_id=%s total_ranges=%s discard_reasons=%s',
            document_code,
            environment,
            configured_id,
            getattr(configuracion, 'id', None),
            getattr(configuracion, 'ambiente_factus', None),
            getattr(dian_config, 'software_id', None),
            len(ranges),
            discard_reasons,
        )
        logger.error(
            'facturacion.numbering_range.resolve.raw_ranges_preview document_code=%s preview=%s',
            document_code,
            [item.raw for item in ranges[:10]],
        )
        raise FactusValidationError(
            f'No se encontró en Factus un rango autorizado y vigente para {document_code} en el ambiente actual.'
        )
    selected_range = next((item for item in ranges if item.factus_id == selected_id), None)
    if selected_range:
        logger.info(
            'facturacion.numbering_range.resolve.selected document_code=%s selected_id=%s prefix=%s valid_from=%s valid_to=%s environment=%s associated_to_software=%s',
            document_code,
            selected_range.factus_id,
            selected_range.prefix,
            selected_range.start_date,
            selected_range.end_date,
            selected_range.environment,
            selected_range.is_associated_to_software,
        )

    if not configuracion:
        configuracion = ConfiguracionFacturacion.objects.create(
            ambiente_factus=environment,
            modo_operacion_electronica='FACTUS_MANAGED',
        )

    if force_refresh or configured_id != selected_id:
        with transaction.atomic():
            locked = ConfiguracionFacturacion.objects.select_for_update().get(pk=configuracion.pk)
            selected_range = selected_range or next((item for item in ranges if item.factus_id == selected_id), None)
            if selected_range:
                _persist_selected_range_metadata(
                    configuracion=locked,
                    selected=selected_range,
                    document_code=document_code,
                    field_name=field_name,
                    environment=environment,
                )

    return selected_id


def get_next_document_sequence(document_code: str) -> InvoiceSequence:
    with transaction.atomic():
        rango = FactusNumberingRange.objects.select_for_update().get(pk=resolve_numbering_range(document_code).pk)
        siguiente = int(rango.from_number)
        rango.from_number = siguiente + 1
        rango.save(update_fields=['from_number'])
    return InvoiceSequence(number=f'{rango.prefix}{siguiente:06d}', numbering_range_id=None)


def get_next_invoice_sequence() -> InvoiceSequence:
    return get_next_document_sequence('FACTURA_VENTA')


def get_next_credit_note_sequence() -> InvoiceSequence:
    return get_next_document_sequence('NOTA_CREDITO')


def get_next_support_document_sequence() -> InvoiceSequence:
    return get_next_document_sequence('DOCUMENTO_SOPORTE')


def get_next_support_adjustment_sequence() -> InvoiceSequence:
    return get_next_document_sequence('NOTA_AJUSTE_DOCUMENTO_SOPORTE')


def get_next_invoice_number() -> str:
    return get_next_invoice_sequence().number
