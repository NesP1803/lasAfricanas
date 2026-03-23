"""Helpers de descarga binaria para recursos electrónicos."""

from __future__ import annotations

from pathlib import Path

import requests
from django.conf import settings


class DownloadResourceError(Exception):
    """Error al resolver contenido binario de un documento electrónico."""


def read_local_media_file(relative_path: str) -> bytes:
    """Lee un archivo relativo a MEDIA_ROOT y devuelve su contenido binario."""
    cleaned = str(relative_path or '').strip()
    if not cleaned:
        raise DownloadResourceError('No hay ruta local configurada para el recurso.')

    full_path = Path(settings.MEDIA_ROOT) / cleaned
    if not full_path.exists() or not full_path.is_file():
        raise DownloadResourceError(f'No existe archivo local en ruta {cleaned}.')

    try:
        return full_path.read_bytes()
    except OSError as exc:
        raise DownloadResourceError(f'No fue posible leer el archivo local {cleaned}.') from exc



def download_remote_file(url: str, timeout: int = 45) -> bytes:
    """Descarga contenido binario desde una URL remota."""
    resolved_url = str(url or '').strip()
    if not resolved_url:
        raise DownloadResourceError('No hay URL de descarga configurada para el recurso.')

    try:
        response = requests.get(resolved_url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.RequestException as exc:
        raise DownloadResourceError('No fue posible descargar el archivo remoto.') from exc
