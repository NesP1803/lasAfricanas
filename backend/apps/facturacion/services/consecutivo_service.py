"""Resolución de rangos DIAN oficiales sincronizados desde Factus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.models import ConfiguracionFacturacion
from apps.facturacion.constants import normalize_local_document_code
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
    prefix: str
    is_active: bool
    is_expired: bool
    is_associated_to_software: bool
    start_date: date | None
    end_date: date | None
    resolution_number: str
    environment: str
    raw: dict[str, Any]


LOCAL_TO_FACTUS_DOCUMENT_ALIASES: dict[str, set[str]] = {
    'FACTURA_VENTA': {'21', 'FACTURA_VENTA', 'FACTURA DE VENTA', 'FACTURA', 'INVOICE', 'BILL'},
    'NOTA_CREDITO': {'22', 'NOTA_CREDITO', 'NOTA CREDITO', 'CREDIT_NOTE', 'CREDIT NOTE', 'NC'},
    'NOTA_DEBITO': {'23', 'NOTA_DEBITO', 'NOTA DEBITO', 'DEBIT_NOTE', 'DEBIT NOTE', 'ND'},
    'DOCUMENTO_SOPORTE': {'24', 'DOCUMENTO_SOPORTE', 'DOCUMENTO SOPORTE', 'SUPPORT_DOCUMENT', 'SUPPORT DOCUMENT'},
    'NOTA_AJUSTE_DOCUMENTO_SOPORTE': {
        '25',
        'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
        'NOTA DE AJUSTE DOCUMENTO SOPORTE',
        'SUPPORT_DOCUMENT_ADJUSTMENT_NOTE',
        'NADS',
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


def _extract_document_tokens(value: Any) -> set[str]:
    raw = str(value or '').strip()
    if not raw:
        return set()
    normalized = (
        raw.upper()
        .replace('-', '_')
        .replace('Á', 'A')
        .replace('É', 'E')
        .replace('Í', 'I')
        .replace('Ó', 'O')
        .replace('Ú', 'U')
    )
    tokens = {normalized, normalized.replace('_', ' '), normalized.replace(' ', '_')}
    mapped_local = normalize_local_document_code(raw)
    if mapped_local:
        tokens.add(mapped_local)
    return {token.strip() for token in tokens if token.strip()}


def _matches_local_document(local_document_code: str, remote_document_code: str) -> bool:
    accepted = LOCAL_TO_FACTUS_DOCUMENT_ALIASES.get(local_document_code, {local_document_code})
    remote_tokens = _extract_document_tokens(remote_document_code)
    if not remote_tokens:
        return local_document_code == 'FACTURA_VENTA'
    return any(token in accepted for token in remote_tokens)


def _normalize_technical_range(raw: dict[str, Any], *, environment: str) -> TechnicalRange:
    factus_id = int(raw.get('id') or raw.get('numbering_range_id') or raw.get('range_id') or 0)
    remote_doc = str(raw.get('document') or raw.get('document_code') or raw.get('document_type') or '').strip()
    document_code = normalize_local_document_code(remote_doc) if remote_doc else 'FACTURA_VENTA'
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
        prefix=str(raw.get('prefix') or '').strip(),
        is_active=is_active,
        is_expired=is_expired,
        is_associated_to_software=is_associated,
        start_date=start_date,
        end_date=end_date,
        resolution_number=str(raw.get('resolution_number') or ''),
        environment=range_env,
        raw=raw,
    )


def _range_match_signature(item: TechnicalRange) -> tuple[str, str, str, str]:
    return (
        str(item.prefix or '').strip().upper(),
        str(item.resolution_number or '').strip().upper(),
        str(item.start_date or ''),
        str(item.end_date or ''),
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
                prefix=item.prefix,
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
    return {
        'FACTURA_VENTA': 'factus_numbering_range_id_factura_venta',
        'NOTA_CREDITO': 'factus_numbering_range_id_nota_credito',
    }.get(document_code, '')


def _fetch_factus_technical_ranges() -> list[TechnicalRange]:
    environment = resolve_factus_environment()
    client = FactusClient()
    payload = client.get_numbering_ranges()
    ranges = [_normalize_technical_range(raw, environment=environment) for raw in _extract_ranges_list(payload)]
    software_payload = client.get_software_numbering_ranges()
    ranges = _merge_software_association(ranges, software_payload, environment=environment)
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
    accepted_doc_aliases = sorted(LOCAL_TO_FACTUS_DOCUMENT_ALIASES.get(document_code, {document_code}))

    by_document = [
        item for item in ranges
        if _matches_local_document(document_code, item.document_code) and item.factus_id > 0 and item.environment == environment
    ]

    for item in ranges:
        if not _matches_local_document(document_code, item.document_code):
            discard_reasons.append(
                f'id={item.factus_id}:descartado_documento={item.document_code}:admitidos={accepted_doc_aliases}'
            )
        elif item.environment != environment:
            discard_reasons.append(f'id={item.factus_id}:descartado_ambiente={item.environment}')
        elif item.factus_id <= 0:
            discard_reasons.append(f'id={item.factus_id}:descartado_id_invalido')
        elif not item.is_associated_to_software:
            discard_reasons.append(f'id={item.factus_id}:descartado_no_asociado_software')
        elif not item.is_active:
            discard_reasons.append(f'id={item.factus_id}:descartado_inactivo_o_expirado')

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


def resolve_electronic_numbering_range_id(document_code: str = 'FACTURA_VENTA') -> int:
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
            'No se encontró en Factus un rango autorizado y vigente para factura electrónica en el ambiente actual.'
        )

    ranges = _fetch_factus_technical_ranges()
    for item in ranges:
        logger.info(
            'facturacion.numbering_range.resolve.range_summary id=%s doc=%s prefix=%s environment=%s active=%s expired=%s valid_to=%s associated_to_software=%s',
            item.factus_id,
            item.document_code,
            item.prefix,
            item.environment,
            item.is_active,
            item.is_expired,
            item.end_date,
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
            'No se encontró en Factus un rango autorizado y vigente para factura electrónica en el ambiente actual.'
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

    if configured_id != selected_id:
        with transaction.atomic():
            locked = ConfiguracionFacturacion.objects.select_for_update().get(pk=configuracion.pk)
            setattr(locked, field_name, selected_id)
            locked.ambiente_factus = environment
            locked.save(update_fields=[field_name, 'ambiente_factus'])
        logger.info(
            'facturacion.numbering_range.resolve.persisted document_code=%s field=%s previous_id=%s selected_id=%s config_id=%s',
            document_code,
            field_name,
            configured_id,
            selected_id,
            configuracion.pk,
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
