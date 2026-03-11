"""Cliente unificado para la API de Factus."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import requests
from decouple import config
from django.utils import timezone

from apps.facturacion_electronica.models import FactusToken

logger = logging.getLogger(__name__)


class FactusAuthError(Exception):
    """Error de autenticación OAuth contra Factus."""


class FactusAPIError(Exception):
    """Error de comunicación o respuesta de la API de Factus."""


class FactusValidationError(Exception):
    """Error de validación de datos para emitir una factura."""


class FactusClient:
    def __init__(self) -> None:
        self.base_url = config('FACTUS_API_URL', default='https://api-sandbox.factus.com.co').rstrip('/')
        self.auth_path = config('FACTUS_AUTH_PATH', default='/oauth/token')
        self.invoice_path = config('FACTUS_INVOICE_PATH', default='/v1/bills/validate')
        self.client_id = config('FACTUS_CLIENT_ID', default='')
        self.client_secret = config('FACTUS_CLIENT_SECRET', default='')
        self.username = config('FACTUS_USERNAME', default='')
        self.password = config('FACTUS_PASSWORD', default='')

    def _auth_payload(self) -> dict[str, str]:
        return {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': self.username,
            'password': self.password,
        }

    def authenticate(self) -> FactusToken:
        auth_url = f'{self.base_url}{self.auth_path}'
        try:
            response = requests.post(
                auth_url,
                data=self._auth_payload(),
                headers={'Accept': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.exception('Error autenticando con Factus.')
            raise FactusAuthError('No fue posible autenticarse con Factus.') from exc
        except ValueError as exc:
            logger.exception('Factus devolvió JSON inválido en OAuth.')
            raise FactusAuthError('Factus devolvió una respuesta inválida en autenticación.') from exc

        access_token = payload.get('access_token')
        if not access_token:
            logger.error('Respuesta OAuth sin access_token: %s', payload)
            raise FactusAuthError('Factus no devolvió access_token válido.')

        expires_in = int(payload.get('expires_in', 0) or 0)
        token = FactusToken.objects.create(
            access_token=access_token,
            token_type=payload.get('token_type', 'Bearer'),
            expires_in=expires_in,
            expires_at=timezone.now() + timedelta(seconds=max(expires_in - 60, 0)),
            scope=payload.get('scope', ''),
            is_active=True,
        )
        FactusToken.objects.exclude(pk=token.pk).update(is_active=False)
        return token

    def get_valid_token(self) -> str:
        token = (
            FactusToken.objects.filter(is_active=True, expires_at__gt=timezone.now())
            .order_by('-created_at')
            .first()
        )
        if token is None:
            token = self.authenticate()
        return token.access_token

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        token = self.get_valid_token()
        url = f"{self.base_url}{path}"
        headers = kwargs.pop('headers', {})
        headers.setdefault('Authorization', f'Bearer {token}')
        headers.setdefault('Accept', 'application/json')

        try:
            response = requests.request(method=method, url=url, headers=headers, timeout=45, **kwargs)
            if response.status_code == 401:
                token = self.authenticate().access_token
                headers['Authorization'] = f'Bearer {token}'
                response = requests.request(method=method, url=url, headers=headers, timeout=45, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.exception('Error invocando Factus endpoint=%s method=%s', path, method)
            raise FactusAPIError('No fue posible comunicarse con Factus.') from exc
        except ValueError as exc:
            logger.exception('JSON inválido de Factus endpoint=%s method=%s', path, method)
            raise FactusAPIError('Factus devolvió una respuesta inválida.') from exc

    def send_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get('items'):
            raise FactusValidationError('La factura no contiene ítems para enviar a Factus.')
        return self.request('POST', self.invoice_path, json=payload)

    def get_invoice(self, number: str) -> dict[str, Any]:
        """Consulta una factura electrónica existente en Factus por número."""
        path = f'/v1/bills/show/{number}'
        return self.request(
            'GET',
            path,
            headers={
                'Content-Type': 'application/json',
            },
        )
