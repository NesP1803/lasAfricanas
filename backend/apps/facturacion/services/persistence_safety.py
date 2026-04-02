"""Utilidades de persistencia defensiva para facturación electrónica."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

from django.db import models

logger = logging.getLogger(__name__)
_BASE64_CHARS_RE = re.compile(r'^[A-Za-z0-9+/=\s]+$')


def safe_truncate(value: Any, max_length: int | None) -> Any:
    """Trunca valores string cuando exceden el límite del campo."""
    if value is None or max_length is None:
        return value
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[:max_length]


def safe_assign_charfield(instance: models.Model, field_name: str, value: Any) -> bool:
    """Asigna de forma segura un CharField/URLField, truncando y retornando si hubo truncado."""
    field = instance._meta.get_field(field_name)
    max_length = getattr(field, "max_length", None)
    original = "" if value is None else str(value)
    truncated = safe_truncate(original, max_length)
    setattr(instance, field_name, truncated)
    return bool(max_length and len(original) > max_length)


def safe_assign_json(instance: models.Model, field_name: str, value: Any) -> None:
    """Asigna JSON garantizando estructura serializable (evita strings JSON gigantes en CharField)."""
    if value is None:
        setattr(instance, field_name, None)
        return
    if isinstance(value, (dict, list)):
        setattr(instance, field_name, value)
        return
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            setattr(instance, field_name, parsed)
            return
        except json.JSONDecodeError:
            setattr(instance, field_name, {"raw": value})
            return
    setattr(instance, field_name, {"raw": str(value)})


def log_model_string_overflow_diagnostics(
    *,
    instance: models.Model,
    venta_id: int | None,
    factura_id: int | None,
    stage: str,
) -> list[dict[str, int | str]]:
    """Inspecciona strings y reporta campos que exceden max_length."""
    overflows: list[dict[str, int | str]] = []
    for field in instance._meta.fields:
        max_length = getattr(field, "max_length", None)
        if not max_length:
            continue
        value = getattr(instance, field.name, None)
        if value is None:
            continue
        text = str(value)
        if len(text) > max_length:
            payload = {
                "field": field.name,
                "length": len(text),
                "max_length": int(max_length),
            }
            overflows.append(payload)
            logger.error(
                "facturacion.persistencia.overflow_detectado stage=%s venta_id=%s factura_id=%s field=%s length=%s max_length=%s",
                stage,
                venta_id,
                factura_id,
                field.name,
                len(text),
                max_length,
            )
    return overflows


def normalize_qr_image_value(value: Any) -> tuple[str, str]:
    """Separa URL remota corta de contenido embebido/base64 para QR."""
    raw = str(value or '').strip()
    if not raw:
        return '', ''
    if raw.startswith('data:image'):
        return '', raw
    parsed = urlparse(raw)
    if parsed.scheme in {'http', 'https'} and parsed.netloc:
        return raw, ''
    return '', raw
