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

    def __init__(self, message: str, *, status_code: int | None = None, provider_detail: str = '') -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_detail = provider_detail


class FactusValidationError(Exception):
    """Error de validación de datos para emitir una factura."""


class FactusClient:
    def __init__(self) -> None:
        self.base_url = config('FACTUS_API_URL', default='https://api-sandbox.factus.com.co').rstrip('/')
        self.auth_path = config('FACTUS_AUTH_PATH', default='/oauth/token')
        self.refresh_path = config('FACTUS_REFRESH_PATH', default='/oauth/token')
        self.invoice_path = config('FACTUS_INVOICE_PATH', default='/v1/bills/validate')
        self.credit_note_path = config('FACTUS_CREDIT_NOTE_PATH', default='/credit-notes/validate')
        self.support_document_path = config('FACTUS_SUPPORT_DOCUMENT_PATH', default='/support-documents/validate')
        self.support_document_adjustment_path = config(
            'FACTUS_SUPPORT_DOCUMENT_ADJUSTMENT_PATH',
            default='/support-document-adjustment-notes/validate',
        )
        self.numbering_ranges_path = config('FACTUS_NUMBERING_RANGES_PATH', default='/v1/numbering-ranges')
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

    def _refresh_payload(self, refresh_token: str) -> dict[str, str]:
        return {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token,
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
        refresh_expires_in = int(payload.get('refresh_expires_in', 0) or 0)
        refresh_token = str(payload.get('refresh_token', '') or '')
        token = FactusToken.objects.create(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=payload.get('token_type', 'Bearer'),
            expires_in=expires_in,
            refresh_expires_in=refresh_expires_in,
            expires_at=timezone.now() + timedelta(seconds=max(expires_in - 60, 0)),
            refresh_expires_at=(
                timezone.now() + timedelta(seconds=max(refresh_expires_in - 60, 0))
                if refresh_expires_in > 0
                else None
            ),
            scope=payload.get('scope', ''),
            is_active=True,
        )
        FactusToken.objects.exclude(pk=token.pk).update(is_active=False)
        return token

    def refresh(self, token: FactusToken) -> FactusToken:
        refresh_token = str(token.refresh_token or '').strip()
        if not refresh_token:
            return self.authenticate()
        if token.refresh_expires_at and token.refresh_expires_at <= timezone.now():
            return self.authenticate()

        refresh_url = f'{self.base_url}{self.refresh_path}'
        try:
            response = requests.post(
                refresh_url,
                data=self._refresh_payload(refresh_token),
                headers={'Accept': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning('Refresh token Factus falló, se intentará authenticate().')
            return self.authenticate()
        except ValueError:
            logger.warning('Refresh token Factus devolvió JSON inválido, se intentará authenticate().')
            return self.authenticate()

        access_token = payload.get('access_token')
        if not access_token:
            logger.warning('Refresh token Factus sin access_token, se intentará authenticate().')
            return self.authenticate()

        expires_in = int(payload.get('expires_in', 0) or 0)
        refresh_expires_in = int(payload.get('refresh_expires_in', 0) or 0)
        new_token = FactusToken.objects.create(
            access_token=access_token,
            refresh_token=str(payload.get('refresh_token', refresh_token) or refresh_token),
            token_type=payload.get('token_type', 'Bearer'),
            expires_in=expires_in,
            refresh_expires_in=refresh_expires_in,
            expires_at=timezone.now() + timedelta(seconds=max(expires_in - 60, 0)),
            refresh_expires_at=(
                timezone.now() + timedelta(seconds=max(refresh_expires_in - 60, 0))
                if refresh_expires_in > 0
                else None
            ),
            scope=payload.get('scope', ''),
            is_active=True,
        )
        FactusToken.objects.exclude(pk=new_token.pk).update(is_active=False)
        return new_token

    def get_valid_token(self) -> str:
        token = (
            FactusToken.objects.filter(is_active=True)
            .order_by('-created_at')
            .first()
        )
        if token is None:
            token = self.authenticate()
        elif token.expires_at <= timezone.now():
            token = self.refresh(token)
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
        except requests.HTTPError as exc:
            response = exc.response
            status_code = getattr(response, 'status_code', None)
            provider_detail = ''
            if response is not None:
                try:
                    parsed = response.json()
                    provider_detail = str(parsed)
                except ValueError:
                    provider_detail = (response.text or '').strip()
            provider_detail = provider_detail[:500]
            logger.warning(
                'Factus rechazó request endpoint=%s method=%s status_code=%s body=%s',
                path,
                method,
                status_code,
                provider_detail,
            )
            detail_suffix = f' Detalle: {provider_detail}' if provider_detail else ''
            raise FactusAPIError(
                f'Factus rechazó la factura.{detail_suffix}',
                status_code=status_code,
                provider_detail=provider_detail,
            ) from exc
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


    def send_credit_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get('items'):
            raise FactusValidationError('La nota crédito no contiene ítems para enviar a Factus.')
        return self.request('POST', self.credit_note_path, json=payload)

    def send_support_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get('supplier'):
            raise FactusValidationError('El documento soporte debe incluir supplier para enviar a Factus.')
        if not payload.get('items'):
            raise FactusValidationError('El documento soporte no contiene ítems para enviar a Factus.')
        return self.request('POST', self.support_document_path, json=payload)


    def send_support_document_adjustment(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get('reference_support_document_number'):
            raise FactusValidationError(
                'La nota de ajuste debe incluir reference_support_document_number para enviar a Factus.'
            )
        if not payload.get('reference_support_document_cufe'):
            raise FactusValidationError(
                'La nota de ajuste debe incluir reference_support_document_cufe para enviar a Factus.'
            )
        if not payload.get('items'):
            raise FactusValidationError('La nota de ajuste no contiene ítems para enviar a Factus.')
        return self.request('POST', self.support_document_adjustment_path, json=payload)


    def get_numbering_ranges(self) -> dict[str, Any]:
        """Consulta los rangos de numeración autorizados en Factus."""
        return self.request('GET', self.numbering_ranges_path)

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
