"""Cliente unificado para la API de Factus."""

from __future__ import annotations

import logging
import base64
from datetime import timedelta
from urllib.parse import urlparse
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

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_detail: str = '',
        provider_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_detail = provider_detail
        self.provider_payload = provider_payload or {}


class FactusPendingDianError(FactusAPIError):
    """Conflicto 409 por documento pendiente de envío/validación ante DIAN."""


class FactusPendingCreditNoteError(FactusAPIError):
    """Conflicto 409 por nota crédito pendiente de envío/validación ante DIAN."""


class FactusValidationError(Exception):
    """Error de validación de datos para emitir una factura."""


class FactusClient:
    def __init__(self) -> None:
        self.base_url = config('FACTUS_API_URL', default='https://api-sandbox.factus.com.co').rstrip('/')
        self.auth_path = config('FACTUS_AUTH_PATH', default='/oauth/token')
        self.refresh_path = config('FACTUS_REFRESH_PATH', default='/oauth/token')
        self.invoice_path = config('FACTUS_INVOICE_PATH', default='/v1/bills/validate')
        self.credit_note_path = config('FACTUS_CREDIT_NOTE_PATH', default='/v1/credit-notes/validate')
        self.credit_note_list_path = config('FACTUS_CREDIT_NOTE_LIST_PATH', default='/v1/credit-notes')
        self.credit_note_show_path = config('FACTUS_CREDIT_NOTE_SHOW_PATH', default='/v1/credit-notes/{number}')
        self.credit_note_download_pdf_path = config(
            'FACTUS_CREDIT_NOTE_DOWNLOAD_PDF_PATH',
            default='/v1/credit-notes/download-pdf/{number}',
        )
        self.credit_note_download_xml_path = config(
            'FACTUS_CREDIT_NOTE_DOWNLOAD_XML_PATH',
            default='/v1/credit-notes/download-xml/{number}',
        )
        self.credit_note_email_content_path = config(
            'FACTUS_CREDIT_NOTE_EMAIL_CONTENT_PATH',
            default='/v1/credit-notes/{number}/email-content',
        )
        self.credit_note_send_email_path = config(
            'FACTUS_CREDIT_NOTE_SEND_EMAIL_PATH',
            default='/v1/credit-notes/send-email/{number}',
        )
        self.credit_note_delete_path = config(
            'FACTUS_CREDIT_NOTE_DELETE_PATH',
            default='/v1/credit-notes/reference/{reference_code}',
        )
        self.support_document_path = config('FACTUS_SUPPORT_DOCUMENT_PATH', default='/support-documents/validate')
        self.support_document_adjustment_path = config(
            'FACTUS_SUPPORT_DOCUMENT_ADJUSTMENT_PATH',
            default='/support-document-adjustment-notes/validate',
        )
        self.numbering_ranges_path = config('FACTUS_NUMBERING_RANGES_PATH', default='/v1/numbering-ranges')
        self.invoice_show_path = config('FACTUS_INVOICE_SHOW_PATH', default='/v1/bills/show/{number}')
        self.invoice_list_path = config('FACTUS_INVOICE_LIST_PATH', default='/v1/bills')
        self.invoice_download_xml_path = config('FACTUS_INVOICE_DOWNLOAD_XML_PATH', default='/v1/bills/download-xml/{number}')
        self.invoice_download_pdf_path = config('FACTUS_INVOICE_DOWNLOAD_PDF_PATH', default='/v1/bills/download-pdf/{number}')
        self.invoice_events_path = config('FACTUS_INVOICE_EVENTS_PATH', default='/v1/bills/events/{number}')
        self.invoice_tacit_acceptance_path = config(
            'FACTUS_INVOICE_TACIT_ACCEPTANCE_PATH',
            default='/v1/bills/acceptance-tacit/{number}',
        )
        self.invoice_delete_path = config('FACTUS_INVOICE_DELETE_PATH', default='/v1/bills/{number}')
        self.invoice_send_email_path = config('FACTUS_INVOICE_SEND_EMAIL_PATH', default='/v1/bills/send-email/{number}')
        self.invoice_email_template_path = config('FACTUS_INVOICE_EMAIL_TEMPLATE_PATH', default='/v1/bills/email-template/{number}')
        self.invoice_custom_pdf_upload_path = config(
            'FACTUS_INVOICE_CUSTOM_PDF_UPLOAD_PATH',
            default='/v1/bills/custom-pdf/{number}',
        )
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
            provider_payload: dict[str, Any] | None = None
            if response is not None:
                try:
                    parsed = response.json()
                    if isinstance(parsed, dict):
                        provider_payload = parsed
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
            pending_message = ''
            if provider_payload:
                pending_message = str(provider_payload.get('message', '') or '').strip().lower()
            if status_code == 409 and 'factura pendiente por enviar a la dian' in pending_message:
                raise FactusPendingDianError(
                    f'Factus reportó la factura pendiente en DIAN.{detail_suffix}',
                    status_code=status_code,
                    provider_detail=provider_detail,
                    provider_payload=provider_payload,
                ) from exc
            if status_code == 409 and (
                'nota crédito pendiente por enviar a la dian' in pending_message
                or 'nota credito pendiente por enviar a la dian' in pending_message
            ):
                raise FactusPendingCreditNoteError(
                    f'Factus reportó una nota crédito pendiente en DIAN.{detail_suffix}',
                    status_code=status_code,
                    provider_detail=provider_detail,
                    provider_payload=provider_payload,
                ) from exc
            raise FactusAPIError(
                f'Factus rechazó la factura.{detail_suffix}',
                status_code=status_code,
                provider_detail=provider_detail,
                provider_payload=provider_payload,
            ) from exc
        except requests.RequestException as exc:
            logger.exception('Error invocando Factus endpoint=%s method=%s', path, method)
            raise FactusAPIError('No fue posible comunicarse con Factus.') from exc
        except ValueError as exc:
            logger.exception('JSON inválido de Factus endpoint=%s method=%s', path, method)
            raise FactusAPIError('Factus devolvió una respuesta inválida.') from exc

    def download_resource(self, url_or_path: str) -> tuple[bytes, bool]:
        """Descarga recurso binario autenticado con token Factus.

        Retorna: (contenido, token_refrescado_por_401)
        """
        parsed = urlparse(url_or_path)
        path = f'{parsed.path}?{parsed.query}' if parsed.query else parsed.path
        if parsed.scheme and parsed.netloc:
            url = url_or_path
        else:
            url = f'{self.base_url}{path}'

        token = self.get_valid_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': '*/*',
        }
        refreshed = False
        try:
            response = requests.get(url, headers=headers, timeout=45)
            if response.status_code == 401:
                refreshed = True
                token = self.authenticate().access_token
                headers['Authorization'] = f'Bearer {token}'
                response = requests.get(url, headers=headers, timeout=45)
            response.raise_for_status()
            return response.content, refreshed
        except requests.HTTPError as exc:
            status_code = getattr(exc.response, 'status_code', None)
            body = (exc.response.text or '')[:500] if exc.response is not None else ''
            logger.warning('Factus rechazó descarga endpoint=%s status=%s body=%s', path, status_code, body)
            raise FactusAPIError(
                'Factus rechazó la descarga.',
                status_code=status_code,
                provider_detail=body,
            ) from exc
        except requests.RequestException as exc:
            logger.exception('Error descargando recurso Factus endpoint=%s', path)
            raise FactusAPIError('No fue posible descargar el recurso en Factus.') from exc

    def create_and_validate_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get('items'):
            raise FactusValidationError('La factura no contiene ítems para enviar a Factus.')
        return self.request('POST', self.invoice_path, json=payload)

    def send_invoice(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Alias legacy: usar create_and_validate_invoice."""
        return self.create_and_validate_invoice(payload)


    def send_credit_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get('items'):
            raise FactusValidationError('La nota crédito no contiene ítems para enviar a Factus.')
        return self.request('POST', self.credit_note_path, json=payload)

    def create_and_validate_credit_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.send_credit_note(payload)
        except FactusAPIError as exc:
            detail = (exc.provider_detail or '').lower()
            should_retry_with_v1 = (
                exc.status_code == 404
                and 'route' in detail
                and 'credit-notes/validate' in detail
                and self.credit_note_path != '/v1/credit-notes/validate'
            )
            if not should_retry_with_v1:
                raise

            logger.warning(
                'Factus credit_note_path=%s no encontrado; reintentando con endpoint /v1/credit-notes/validate',
                self.credit_note_path,
            )
            original_path = self.credit_note_path
            try:
                self.credit_note_path = '/v1/credit-notes/validate'
                return self.send_credit_note(payload)
            finally:
                self.credit_note_path = original_path

    def list_credit_notes(self, **params: Any) -> dict[str, Any]:
        raw_params = params or {}
        translated_params: dict[str, Any] = {}
        mapping = {
            'reference_code': 'filter[reference_code]',
            'number': 'filter[number]',
            'status': 'filter[status]',
            'prefix': 'filter[prefix]',
            'identification': 'filter[identification]',
            'names': 'filter[names]',
        }
        for key, value in raw_params.items():
            if value in (None, ''):
                continue
            translated_params[mapping.get(key, key)] = value
        return self.request('GET', self.credit_note_list_path, params=translated_params or None)

    def get_credit_note_by_reference_code(self, reference_code: str, *, bill_number: str | None = None) -> dict[str, Any]:
        filters: dict[str, Any] = {'reference_code': reference_code}
        if bill_number:
            filters['bill_number'] = bill_number
        return self.list_credit_notes(**filters)

    def get_credit_note_by_reference_code(self, reference_code: str, *, bill_number: str | None = None) -> dict[str, Any]:
        filters: dict[str, Any] = {'reference_code': reference_code}
        if bill_number:
            filters['bill_number'] = bill_number
        return self.list_credit_notes(**filters)

    def get_credit_note(self, number: str) -> dict[str, Any]:
        return self.request('GET', self.credit_note_show_path.format(number=number))

    def download_credit_note_pdf(self, number: str) -> bytes:
        payload = self.request('GET', self.credit_note_download_pdf_path.format(number=number))
        content = self._decode_base64_payload(payload, field='pdf_base_64_encoded')
        if content:
            return content
        fallback, _ = self.download_resource(self.credit_note_download_pdf_path.format(number=number))
        return fallback

    def download_credit_note_xml(self, number: str) -> bytes:
        payload = self.request('GET', self.credit_note_download_xml_path.format(number=number))
        content = self._decode_base64_payload(payload, field='xml_base_64_encoded')
        if content:
            return content
        fallback, _ = self.download_resource(self.credit_note_download_xml_path.format(number=number))
        return fallback

    def _decode_base64_payload(self, payload: dict[str, Any], *, field: str) -> bytes:
        data = payload.get('data', payload)
        if not isinstance(data, dict):
            return b''
        encoded = str(data.get(field) or payload.get(field) or '').strip()
        if not encoded:
            return b''
        try:
            return base64.b64decode(encoded)
        except Exception:
            logger.warning('No fue posible decodificar base64 para credit-note field=%s', field)
            return b''

    def get_credit_note_email_content(self, number: str) -> dict[str, Any]:
        return self.request('GET', self.credit_note_email_content_path.format(number=number))

    def send_credit_note_email(self, number: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request('POST', self.credit_note_send_email_path.format(number=number), json=payload or {})

    def delete_credit_note(self, reference_code: str) -> dict[str, Any]:
        return self.request('DELETE', self.credit_note_delete_path.format(reference_code=reference_code))

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
        path = self.invoice_show_path.format(number=number)
        return self.request(
            'GET',
            path,
            headers={
                'Content-Type': 'application/json',
            },
        )

    def get_invoice_downloads(self, number: str) -> dict[str, Any]:
        """Consulta enlaces de descarga XML/PDF de una factura en Factus."""
        path = self.invoice_download_pdf_path.format(number=number)
        return self.request(
            'GET',
            path,
            headers={
                'Content-Type': 'application/json',
            },
        )

    def download_invoice_xml(self, number: str) -> bytes:
        path = self.invoice_download_xml_path.format(number=number)
        content, _ = self.download_resource(path)
        return content

    def download_invoice_pdf(self, number: str) -> bytes:
        path = self.invoice_download_pdf_path.format(number=number)
        content, _ = self.download_resource(path)
        return content

    def list_invoices(self, *, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request('GET', self.invoice_list_path, params=filters or {})

    def get_invoice_email_content(self, number: str) -> dict[str, Any]:
        return self.request('GET', self.invoice_email_template_path.format(number=number))

    def delete_invoice(self, number: str) -> dict[str, Any]:
        return self.request('DELETE', self.invoice_delete_path.format(number=number))

    def get_invoice_events(self, number: str) -> dict[str, Any]:
        return self.request('GET', self.invoice_events_path.format(number=number))

    def tacit_acceptance(self, number: str) -> dict[str, Any]:
        return self.request('POST', self.invoice_tacit_acceptance_path.format(number=number), json={})

    def send_invoice_email(self, number: str, email: str | None = None) -> dict[str, Any]:
        payload = {'email': email} if email else None
        return self.request('POST', self.invoice_send_email_path.format(number=number), json=payload)

    def get_invoice_email_template(self, number: str) -> dict[str, Any]:
        """Alias legacy: usar get_invoice_email_content."""
        return self.get_invoice_email_content(number)

    def upload_custom_pdf(self, number: str, pdf_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
        token = self.get_valid_token()
        url = f"{self.base_url}{self.invoice_custom_pdf_upload_path.format(number=number)}"
        files = {
            'file': (filename or f'{number}.pdf', pdf_bytes, 'application/pdf'),
        }
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        try:
            response = requests.post(url, headers=headers, files=files, timeout=45)
            if response.status_code == 401:
                token = self.authenticate().access_token
                headers['Authorization'] = f'Bearer {token}'
                response = requests.post(url, headers=headers, files=files, timeout=45)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            detail = (exc.response.text or '')[:500] if exc.response is not None else ''
            raise FactusAPIError(
                f'Factus rechazó el PDF personalizado. Detalle: {detail}' if detail else 'Factus rechazó el PDF personalizado.',
                status_code=getattr(exc.response, 'status_code', None),
                provider_detail=detail,
            ) from exc
        except requests.RequestException as exc:
            raise FactusAPIError('No fue posible subir PDF personalizado a Factus.') from exc
