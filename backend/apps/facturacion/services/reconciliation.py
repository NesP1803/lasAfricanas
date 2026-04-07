from __future__ import annotations

import logging
from typing import Any

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.electronic_state_machine import map_factus_status
from apps.facturacion.services.factus_client import FactusValidationError
from apps.ventas.models import Venta

logger = logging.getLogger(__name__)


def extract_factus_data(response_json: dict[str, Any]) -> dict[str, str]:
    data = response_json.get('data', response_json)
    bill = data.get('bill', data)
    document = bill.get('document', {}) if isinstance(bill.get('document', {}), dict) else {}
    file_data = bill.get('files', {}) if isinstance(bill.get('files', {}), dict) else {}
    return {
        'cufe': str(bill.get('cufe') or document.get('cufe') or data.get('cufe', '')).strip(),
        'uuid': str(bill.get('uuid') or document.get('uuid') or data.get('uuid', '')).strip(),
        'number': str(bill.get('number') or document.get('number') or data.get('number', '')).strip(),
        'reference_code': str(
            bill.get('reference_code') or document.get('reference_code') or data.get('reference_code', '')
        ).strip(),
        'xml_url': str(
            bill.get('xml_url') or file_data.get('xml_url') or document.get('xml_url') or data.get('xml_url', '')
        ).strip(),
        'pdf_url': str(
            bill.get('pdf_url') or file_data.get('pdf_url') or document.get('pdf_url') or data.get('pdf_url', '')
        ).strip(),
        'qr': str(bill.get('qr', data.get('qr', ''))).strip(),
        'qr_image': str(bill.get('qr_image', data.get('qr_image', ''))).strip(),
        'qr_url': str(bill.get('qr_url', data.get('qr_url', ''))).strip(),
        'public_url': str(bill.get('public_url', data.get('public_url', ''))).strip(),
        'zip_key': str(bill.get('zip_key', data.get('zip_key', ''))).strip(),
        'status': map_factus_status(response_json)[0],
        'estado_factus_raw': map_factus_status(response_json)[1],
    }


def merge_factus_fields(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    for key, value in extra.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def assert_emitted_document_matches_sale(
    *,
    venta: Venta,
    fields: dict[str, str],
    expected_number: str,
    expected_reference_code: str,
) -> None:
    number = str(fields.get('number') or '').strip()
    reference_code = str(fields.get('reference_code') or '').strip()
    expected_number = str(expected_number or '').strip()
    expected_reference_code = str(expected_reference_code or '').strip()

    expected_prefix = ''.join(char for char in expected_number if char.isalpha())
    expected_sequence = ''.join(char for char in expected_number if char.isdigit())
    returned_prefix = ''.join(char for char in number if char.isalpha())
    returned_sequence = ''.join(char for char in number if char.isdigit())
    has_prefix_mismatch = bool(expected_prefix and returned_prefix and expected_prefix != returned_prefix)
    has_sequence_mismatch = bool(expected_sequence and returned_sequence and expected_sequence != returned_sequence)

    logger.info(
        'facturar_venta.validacion_documental venta_id=%s expected_reference=%s expected_number=%s '
        'returned_number=%s returned_reference_code=%s factus_status=%s',
        venta.id,
        expected_reference_code,
        expected_number,
        number,
        reference_code,
        fields.get('status', ''),
    )

    if number and expected_number and (number != expected_number or has_prefix_mismatch or has_sequence_mismatch):
        raise FactusValidationError(
            f'Factus devolvió number={number} pero la venta {venta.id} esperaba {expected_number}. '
            'Se bloquea la asociación para evitar enlazar CUFE/QR de otro documento.'
        )

    if number and FacturaElectronica.objects.filter(number=number).exclude(venta=venta).exists():
        raise FactusValidationError(
            f'Factus devolvió number={number}, pero ya está asociado a otra venta. '
            'Se bloquea la asociación para evitar enlazar CUFE/QR de otro documento.'
        )

    if reference_code and expected_reference_code and reference_code != expected_reference_code:
        raise FactusValidationError(
            f'Factus devolvió reference_code={reference_code} pero la venta {venta.id} esperaba '
            f'{expected_reference_code}. Se bloquea la asociación para evitar cruces entre ventas.'
        )

    if reference_code and FacturaElectronica.objects.filter(reference_code=reference_code).exclude(venta=venta).exists():
        raise FactusValidationError(
            f'Factus devolvió reference_code={reference_code}, pero ya está asociado a otra venta. '
            'Se bloquea la asociación para evitar cruces entre ventas.'
        )


PERSISTABLE_FACTURA_FIELDS = {
    'cufe',
    'uuid',
    'number',
    'reference_code',
    'xml_url',
    'pdf_url',
    'public_url',
    'qr',
    'qr_image',
    'status',
    'estado_factus_raw',
}
