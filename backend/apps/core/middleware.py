import json

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

                Auditoria.objects.create(
                    usuario=usuario,
                    usuario_nombre=usuario_nombre,
                    accion=accion,
                    modelo=request.resolver_match.view_name if request.resolver_match else '',
                    objeto_id='',
                    notas=f"{request.method} {request.path}",
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
        if usuario:
            return usuario.get_username()

        if request.path.startswith('/api/auth/login/') and request.body:
            try:
                body = json.loads(request.body.decode('utf-8'))
                return body.get('username', 'Desconocido')
            except json.JSONDecodeError:
                return 'Desconocido'

        return 'Sistema'

    def _get_ip(self, request):
        return request.META.get('REMOTE_ADDR')
