"""Descarga y persistencia local de XML/PDF de facturas electrónicas."""

from __future__ import annotations

from pathlib import Path

import requests
from django.conf import settings

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.exceptions import DescargaFacturaError


def _download_invoice_file(factura: FacturaElectronica, url: str, folder: str, extension: str, field: str) -> str:
    if not url:
        raise DescargaFacturaError(f'La factura {factura.number} no tiene URL de descarga para {extension.upper()}.')

    relative_path = Path('facturas') / folder / f'{factura.number}.{extension}'
    full_path = Path(settings.MEDIA_ROOT) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, timeout=45)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DescargaFacturaError(
            f'No fue posible descargar el archivo {extension.upper()} de la factura {factura.number}.'
        ) from exc

    full_path.write_bytes(response.content)
    setattr(factura, field, str(relative_path))
    factura.save(update_fields=[field, 'updated_at'])
    return str(relative_path)


def download_xml(factura: FacturaElectronica) -> str:
    """Descarga y almacena localmente el XML de la factura."""
    return _download_invoice_file(
        factura=factura,
        url=factura.xml_url,
        folder='xml',
        extension='xml',
        field='xml_local_path',
    )


def download_pdf(factura: FacturaElectronica) -> str:
    """Descarga y almacena localmente el PDF de la factura."""
    return _download_invoice_file(
        factura=factura,
        url=factura.pdf_url,
        folder='pdf',
        extension='pdf',
        field='pdf_local_path',
    )
