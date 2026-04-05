"""Helpers para resolver entorno y base URL efectiva de Factus."""

from __future__ import annotations

from decouple import config
from django.conf import settings

FACTUS_SANDBOX_BASE_URL = 'https://api-sandbox.factus.com.co'
FACTUS_PRODUCTION_BASE_URL = 'https://api.factus.com.co'


def resolve_factus_environment() -> str:
    raw = str(getattr(settings, 'FACTUS_ENV', 'sandbox')).strip().lower()
    return 'PRODUCTION' if raw in {'prod', 'production'} else 'SANDBOX'


def resolve_factus_base_url() -> str:
    explicit_url = str(config('FACTUS_API_URL', default='')).strip()
    if explicit_url:
        return explicit_url.rstrip('/')
    if resolve_factus_environment() == 'PRODUCTION':
        return FACTUS_PRODUCTION_BASE_URL
    return FACTUS_SANDBOX_BASE_URL
