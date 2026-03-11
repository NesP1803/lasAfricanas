"""Generación de QR DIAN para facturas electrónicas."""

from __future__ import annotations

from django.core.files.base import ContentFile

import qrcode


def generate_qr_dian(numero: str, cufe: str) -> ContentFile:
    """Genera imagen QR DIAN desde el CUFE y retorna un ContentFile listo para guardar."""
    qr_content = f'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={cufe}'
    image = qrcode.make(qr_content)

    buffer = ContentFile(b'')
    image.save(buffer, format='PNG')
    buffer.seek(0)
    buffer.name = f'{numero}.png'
    return buffer
