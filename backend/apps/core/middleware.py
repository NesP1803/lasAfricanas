import json
from dataclasses import dataclass

from django.http import RawPostDataException

from .models import Auditoria


@dataclass(frozen=True)
class AuditRule:
    modulo: str
    entidad: str
    descripcion: str


DEFAULT_ACTION_TEXT = {
    'CREAR': 'Se creó',
    'ACTUALIZAR': 'Se actualizó',
    'ELIMINAR': 'Se eliminó',
    'LOGIN': 'Inicio de sesión',
    'LOGOUT': 'Cierre de sesión',
}


# Registro declarativo y extensible por módulo/entidad.
AUDIT_REGISTRY = {
    'ventas': {
        'clientes': AuditRule('ventas', 'cliente', 'cliente'),
        'ventas': AuditRule('ventas', 'venta', 'venta'),
        'caja': AuditRule('ventas', 'venta', 'venta'),
        'solicitudes-descuento': AuditRule('ventas', 'solicitud-descuento', 'solicitud de descuento'),
    },
    'inventario': {
        'productos': AuditRule('inventario', 'producto', 'producto'),
        'categorias': AuditRule('inventario', 'categoria', 'categoría'),
        'proveedores': AuditRule('inventario', 'proveedor', 'proveedor'),
        'movimientos': AuditRule('inventario', 'movimiento', 'movimiento de inventario'),
        'productos-favoritos': AuditRule('inventario', 'producto-favorito', 'producto favorito'),
    },
    'taller': {
        'mecanicos': AuditRule('taller', 'mecanico', 'mecánico'),
        'motos': AuditRule('taller', 'moto', 'moto'),
        'ordenes-taller': AuditRule('taller', 'orden-taller', 'orden de taller'),
    },
    'facturacion': {
        'facturacion': AuditRule('facturacion', 'factura-electronica', 'factura electrónica'),
    },
    'notas-credito': {
        'notas-credito': AuditRule('notas-credito', 'nota-credito', 'nota crédito electrónica'),
    },
    'documentos-soporte': {
        'documentos-soporte': AuditRule('documentos-soporte', 'documento-soporte', 'documento soporte electrónico'),
    },
    'configuracion': {
        'configuracion-empresa': AuditRule('configuracion', 'configuracion-empresa', 'configuración de empresa'),
        'configuracion-facturacion': AuditRule('configuracion', 'configuracion-facturacion', 'configuración de facturación'),
        'impuestos': AuditRule('configuracion', 'impuesto', 'impuesto'),
        'configuracion': AuditRule('configuracion', 'configuracion-dian', 'configuración DIAN'),
    },
    'core': {
        'usuarios': AuditRule('core', 'usuario', 'usuario'),
        'auditoria': AuditRule('core', 'auditoria', 'auditoría'),
    },
}


class AuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith('/api/') and request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            if request.path.startswith('/api/auth/refresh/'):
                return response
            if request.path.startswith('/api/auth/login/'):
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
                    notas=self._build_notas(request, response, accion, objeto_id),
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

        if request.path.startswith('/api/auth/login/'):
            username = request.POST.get('username')
            return username or 'Desconocido'

        try:
            raw = request.body
        except RawPostDataException:
            return 'Sistema'

        if raw:
            try:
                body = json.loads(raw.decode('utf-8'))
                return body.get('username') or body.get('user') or body.get('usuario') or 'Sistema'
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

    def _build_notas(self, request, response, accion, objeto_id):
        if request.path.startswith('/api/auth/login/'):
            return 'Inicio de sesión'

        rule = self._resolve_rule(request)
        descripcion = rule.descripcion if rule else 'registro'
        action_text = DEFAULT_ACTION_TEXT.get(accion, 'Se realizó una acción')

        request_data = self._get_request_data(request)
        response_data = response.data if hasattr(response, 'data') and isinstance(response.data, dict) else {}
        etiqueta = self._build_label(response_data, request_data)

        if etiqueta:
            return f'{action_text} {descripcion}: {etiqueta}'
        if objeto_id:
            return f'{action_text} {descripcion} (ID {objeto_id})'
        return f'{action_text} {descripcion}'

    def _resolve_rule(self, request):
        parts = [part for part in request.path.split('/') if part]
        if len(parts) < 2:
            return None
        resource = parts[1]

        for modulo, mappings in AUDIT_REGISTRY.items():
            if resource in mappings:
                return mappings[resource]

        if resource == 'configuracion' and len(parts) >= 3:
            return AUDIT_REGISTRY['configuracion'].get('configuracion')

        return None

    def _get_request_data(self, request):
        try:
            raw = request.body
        except RawPostDataException:
            return {}

        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode('utf-8'))
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _build_label(self, data, request_data):
        merged = {**request_data, **data}

        if merged.get('nombre') and merged.get('codigo'):
            return f"{merged['nombre']} (código {merged['codigo']})"

        if merged.get('nombre') and merged.get('numero_documento'):
            return f"{merged['nombre']} (doc. {merged['numero_documento']})"

        if merged.get('numero'):
            return str(merged['numero'])

        if merged.get('number'):
            return str(merged['number'])

        for key in ('nombre', 'razon_social', 'descripcion', 'titulo', 'codigo', 'placa', 'username', 'email'):
            if merged.get(key):
                return str(merged[key])

        return ''
