import json
from datetime import timedelta
from urllib import error, parse, request

from decouple import config
from django.utils import timezone

from apps.facturacion_electronica.models import FactusToken


class FactusAPIError(Exception):
    pass


class FactusClient:
    def __init__(self):
        self.base_url = config('FACTUS_BASE_URL', default='https://api-sandbox.factus.com.co')
        self.auth_path = config('FACTUS_AUTH_PATH', default='/oauth/token')
        self.invoice_path = config('FACTUS_INVOICE_PATH', default='/v1/bills/validate')
        self.client_id = config('FACTUS_CLIENT_ID', default='')
        self.client_secret = config('FACTUS_CLIENT_SECRET', default='')
        self.username = config('FACTUS_USERNAME', default='')
        self.password = config('FACTUS_PASSWORD', default='')

    def authenticate(self) -> FactusToken:
        auth_url = f'{self.base_url}{self.auth_path}'
        body = parse.urlencode(
            {
                'grant_type': 'password',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'username': self.username,
                'password': self.password,
            }
        ).encode('utf-8')
        req = request.Request(auth_url, data=body, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        try:
            with request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except error.HTTPError as exc:
            detail = exc.read().decode('utf-8')
            raise FactusAPIError(f'Error autenticando con Factus: {detail}') from exc
        except error.URLError as exc:
            raise FactusAPIError(f'Error de red autenticando con Factus: {exc.reason}') from exc

        expires_in = int(payload.get('expires_in', 0))
        token = FactusToken.objects.create(
            access_token=payload['access_token'],
            token_type=payload.get('token_type', 'Bearer'),
            expires_in=expires_in,
            expires_at=timezone.now() + timedelta(seconds=max(expires_in - 60, 0)),
            scope=payload.get('scope', ''),
        )
        FactusToken.objects.exclude(pk=token.pk).update(is_active=False)
        return token

    def get_valid_token(self) -> str:
        token = (
            FactusToken.objects.filter(is_active=True, expires_at__gt=timezone.now())
            .order_by('-created_at')
            .first()
        )
        if not token:
            token = self.authenticate()
        return token.access_token

    def create_invoice(self, payload: dict) -> dict:
        token = self.get_valid_token()
        url = f'{self.base_url}{self.invoice_path}'
        raw_payload = json.dumps(payload).encode('utf-8')
        req = request.Request(url, data=raw_payload, method='POST')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')

        try:
            with request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except error.HTTPError as exc:
            detail = exc.read().decode('utf-8')
            raise FactusAPIError(f'Error creando factura en Factus: {detail}') from exc
        except error.URLError as exc:
            raise FactusAPIError(f'Error de red enviando factura a Factus: {exc.reason}') from exc
