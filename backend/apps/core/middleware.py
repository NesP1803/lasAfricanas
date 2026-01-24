import json
from django.http import RawPostDataException

from .models import Auditoria


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith('/api/') and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            if request.path.startswith('/api/auth/refresh/'):
                return response

            if response.status_code < 400:
                accion = self._map_action(request)
                usuario = request.user if request.user.is_authenticated else None
                usuario_nombre = self._get_usuario_nombre(request, usuario)
                objeto_id = self._get_objeto_id(request, response)
                modelo = request.resolver_match.view_name if request.resolver_match else ''

                Auditoria.objects.create(
                    usuario=usuario,
                    usuario_nombre=usuario_nombre,
                    accion=accion,
                    modelo=modelo,
                    objeto_id=objeto_id,
                    notas=self._build_notas(request, response, accion, modelo, objeto_id),
                    ip_address=self._get_ip(request),
                )

        return response

    def _map_action(self, request):
        if request.path.startswith('/api/auth/login/'):
            return 'LOGIN'
        if request.method == 'POST':
            return 'CREAR'
        if request.method in {'PUT', 'PATCH'}:
            return 'ACTUALIZAR'
        if request.method == 'DELETE':
            return 'ELIMINAR'
        return 'OTRO'

    def _get_usuario_nombre(self, request, usuario):
        # Si ya está autenticado, úsalo
        if usuario:
            return usuario.get_username()

        # ✅ Login: NO leer request.body (rompe DRF). Intenta por POST (si es form) o deja genérico.
        if request.path.startswith('/api/auth/login/'):
            username = request.POST.get('username')  # si algún día mandas form-data
            return username or 'Desconocido'

        # Para otras rutas, intenta leer body SOLO si aún es accesible
        try:
            raw = request.body
        except RawPostDataException:
            return 'Sistema'

        if raw:
            try:
                body = json.loads(raw.decode('utf-8'))
                # intenta por convenciones comunes
                return (
                    body.get('username')
                    or body.get('user')
                    or body.get('usuario')
                    or 'Sistema'
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                return 'Sistema'

        return 'Sistema'

    def _get_ip(self, request):
        return request.META.get('REMOTE_ADDR')

    def _get_objeto_id(self, request, response):
        if request.resolver_match and request.resolver_match.kwargs.get('pk'):
            return str(request.resolver_match.kwargs.get('pk'))
        if hasattr(response, 'data') and isinstance(response.data, dict):
            possible_id = response.data.get('id') or response.data.get('pk')
            if possible_id is not None:
                return str(possible_id)
        return ''

    def _build_notas(self, request, response, accion, modelo, objeto_id):
        if request.path.startswith('/api/auth/login/'):
            return 'Inicio de sesión'

        etiqueta = self._get_etiqueta_objeto(response)
        descripcion_modelo = self._humanize_modelo(modelo) or 'registro'
        accion_texto = {
            'CREAR': 'Se creó',
            'ACTUALIZAR': 'Se actualizó',
            'ELIMINAR': 'Se eliminó',
            'LOGIN': 'Inicio de sesión',
            'LOGOUT': 'Cierre de sesión',
        }.get(accion, 'Se realizó una acción')

        if etiqueta:
            return f"{accion_texto} {descripcion_modelo}: {etiqueta}"
        if objeto_id:
            return f"{accion_texto} {descripcion_modelo} (ID {objeto_id})"
        return f"{accion_texto} {descripcion_modelo}"

    def _get_etiqueta_objeto(self, response):
        if not hasattr(response, 'data') or not isinstance(response.data, dict):
            return ''
        data = response.data
        for key in ('nombre', 'razon_social', 'descripcion', 'titulo', 'codigo', 'sku'):
            value = data.get(key)
            if value:
                return str(value)
        if data.get('prefijo_factura') and data.get('numero_factura'):
            return f"{data.get('prefijo_factura')}-{data.get('numero_factura')}"
        return ''

    def _humanize_modelo(self, modelo):
        if not modelo:
            return ''
        return (
            modelo.replace('_', ' ')
            .replace('-', ' ')
            .replace('api:', '')
            .replace('viewset', '')
            .strip()
        )
