import json
from django.http import RawPostDataException

from apps.inventario.models import Categoria, MovimientoInventario, Producto, Proveedor
from apps.taller.models import Mecanico, Moto, OrdenTaller
from apps.usuarios.models import Usuario
from apps.ventas.models import Cliente, Venta

from .models import Auditoria


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

        view_name = self._get_view_name(request)
        modelo_slug = self._get_modelo_slug(view_name)
        accion_detalle = self._get_action_name(view_name, modelo_slug)
        descripcion_modelo = self._humanize_modelo(modelo_slug) or 'registro'
        request_data = self._get_request_data(request)
        etiqueta = self._build_etiqueta(modelo_slug, response, request_data, objeto_id)

        if modelo_slug == 'orden-taller' and accion_detalle in {'agregar_repuesto', 'quitar_repuesto', 'facturar'}:
            return self._build_notas_orden_taller(
                accion_detalle,
                response,
                request_data,
                etiqueta,
            )

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

    def _get_view_name(self, request):
        if request.resolver_match and request.resolver_match.view_name:
            return request.resolver_match.view_name
        return ''

    def _get_modelo_slug(self, view_name):
        if not view_name:
            return ''
        if ':' in view_name:
            view_name = view_name.split(':', 1)[1]
        candidatos = [
            'configuracion-empresa',
            'configuracion-facturacion',
            'orden-taller',
            'movimiento',
            'producto',
            'proveedor',
            'categoria',
            'cliente',
            'venta',
            'usuario',
            'mecanico',
            'moto',
            'impuesto',
            'auditoria',
        ]
        for candidato in candidatos:
            if view_name.startswith(f"{candidato}-") or view_name == candidato:
                return candidato
        return view_name.split('-', 1)[0]

    def _get_action_name(self, view_name, modelo_slug):
        if not view_name or not modelo_slug:
            return ''
        if ':' in view_name:
            view_name = view_name.split(':', 1)[1]
        if view_name.startswith(f"{modelo_slug}-"):
            return view_name.replace(f"{modelo_slug}-", '', 1)
        return ''

    def _get_request_data(self, request):
        try:
            raw = request.body
        except RawPostDataException:
            return {}

        if not raw:
            return {}
        try:
            return json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _build_etiqueta(self, modelo_slug, response, request_data, objeto_id):
        data = {}
        if hasattr(response, 'data') and isinstance(response.data, dict):
            data = response.data

        if modelo_slug == 'producto':
            return self._format_producto(data, request_data)
        if modelo_slug == 'categoria':
            return self._format_nombre_basico(data, request_data)
        if modelo_slug == 'proveedor':
            return self._format_proveedor(data, request_data)
        if modelo_slug == 'cliente':
            return self._format_cliente(data, request_data)
        if modelo_slug == 'usuario':
            return self._format_usuario(data, request_data)
        if modelo_slug == 'mecanico':
            return self._format_nombre_basico(data, request_data)
        if modelo_slug == 'moto':
            return self._format_moto(data, request_data)
        if modelo_slug == 'orden-taller':
            return self._format_orden_taller(data, request_data)
        if modelo_slug == 'movimiento':
            return self._format_movimiento(data, request_data)
        if modelo_slug == 'venta':
            return self._format_venta(data, request_data)

        etiqueta = self._get_etiqueta_objeto(data)
        if not etiqueta and objeto_id:
            etiqueta = self._lookup_etiqueta_db(modelo_slug, objeto_id)
        return etiqueta

    def _get_etiqueta_objeto(self, data):
        for key in ('nombre', 'razon_social', 'descripcion', 'titulo', 'codigo', 'sku'):
            value = data.get(key)
            if value:
                return str(value)
        if data.get('prefijo_factura') and data.get('numero_factura'):
            return f"{data.get('prefijo_factura')}-{data.get('numero_factura')}"
        return ''

    def _format_nombre_basico(self, data, request_data):
        nombre = data.get('nombre') or request_data.get('nombre')
        return str(nombre) if nombre else ''

    def _format_producto(self, data, request_data):
        nombre = data.get('nombre') or request_data.get('nombre')
        codigo = data.get('codigo') or request_data.get('codigo')
        if nombre and codigo:
            return f"{nombre} (código {codigo})"
        if nombre:
            return str(nombre)
        if codigo:
            return f"Código {codigo}"
        return ''

    def _format_proveedor(self, data, request_data):
        nombre = data.get('nombre') or data.get('razon_social') or request_data.get('nombre')
        nit = data.get('nit') or request_data.get('nit')
        if nombre and nit:
            return f"{nombre} (NIT {nit})"
        return str(nombre) if nombre else ''

    def _format_cliente(self, data, request_data):
        nombre = data.get('nombre') or request_data.get('nombre')
        documento = data.get('numero_documento') or request_data.get('numero_documento')
        if nombre and documento:
            return f"{nombre} (doc. {documento})"
        return str(nombre) if nombre else ''

    def _format_usuario(self, data, request_data):
        username = data.get('username') or request_data.get('username') or request_data.get('usuario')
        email = data.get('email') or request_data.get('email')
        if username and email:
            return f"{username} ({email})"
        return str(username) if username else ''

    def _format_moto(self, data, request_data):
        placa = data.get('placa') or request_data.get('placa')
        marca = data.get('marca') or request_data.get('marca')
        modelo = data.get('modelo') or request_data.get('modelo')
        detalle = ' '.join(filter(None, [marca, modelo]))
        if placa and detalle:
            return f"{placa} ({detalle})"
        return str(placa) if placa else ''

    def _format_orden_taller(self, data, request_data):
        moto_placa = data.get('moto_placa') or request_data.get('moto_placa')
        moto_marca = data.get('moto_marca') or request_data.get('moto_marca')
        moto_modelo = data.get('moto_modelo') or request_data.get('moto_modelo')
        mecanico = data.get('mecanico_nombre') or request_data.get('mecanico_nombre')
        moto_detalle = ' '.join(filter(None, [moto_marca, moto_modelo]))
        piezas = []
        if moto_placa:
            piezas.append(f"moto {moto_placa}" + (f" ({moto_detalle})" if moto_detalle else ''))
        if mecanico:
            piezas.append(f"mecánico {mecanico}")
        return ' / '.join(piezas)

    def _format_movimiento(self, data, request_data):
        producto = data.get('producto_nombre') or request_data.get('producto_nombre')
        tipo = data.get('tipo_display') or request_data.get('tipo_display')
        cantidad = data.get('cantidad') or request_data.get('cantidad')
        partes = []
        if tipo:
            partes.append(str(tipo).lower())
        if cantidad:
            partes.append(str(cantidad))
        if producto:
            partes.append(f"de {producto}")
        return ' '.join(partes).strip()

    def _format_venta(self, data, request_data):
        numero = data.get('numero_comprobante') or request_data.get('numero_comprobante')
        cliente = data.get('cliente_nombre')
        if not cliente and isinstance(data.get('cliente_info'), dict):
            cliente = data['cliente_info'].get('nombre')
        if numero and cliente:
            return f"{numero} (cliente {cliente})"
        return str(numero) if numero else ''

    def _get_repuesto_nombre(self, data, request_data):
        producto_id = request_data.get('producto')
        if not producto_id:
            return ''
        repuestos = data.get('repuestos') if isinstance(data.get('repuestos'), list) else []
        for repuesto in repuestos:
            if str(repuesto.get('producto')) == str(producto_id):
                return repuesto.get('producto_nombre') or ''
        return ''

    def _build_notas_orden_taller(self, accion_detalle, response, request_data, orden_info):
        data = response.data if hasattr(response, 'data') and isinstance(response.data, dict) else {}
        repuesto_nombre = self._get_repuesto_nombre(data, request_data)
        if accion_detalle == 'agregar_repuesto':
            detalle_repuesto = f"repuesto {repuesto_nombre}" if repuesto_nombre else 'un repuesto'
            detalle_orden = f" a la orden de taller {orden_info}" if orden_info else ' a la orden de taller'
            return f"Se agregó {detalle_repuesto}{detalle_orden}"
        if accion_detalle == 'quitar_repuesto':
            detalle_repuesto = f"repuesto {repuesto_nombre}" if repuesto_nombre else 'un repuesto'
            detalle_orden = f" de la orden de taller {orden_info}" if orden_info else ' de la orden de taller'
            return f"Se quitó {detalle_repuesto}{detalle_orden}"
        if accion_detalle == 'facturar':
            venta_numero = data.get('venta_numero')
            detalle_orden = f"la orden de taller {orden_info}" if orden_info else 'la orden de taller'
            if venta_numero:
                return f"Se facturó {detalle_orden} (venta {venta_numero})"
            return f"Se facturó {detalle_orden}"
        return 'Se actualizó orden de taller'

    def _lookup_etiqueta_db(self, modelo_slug, objeto_id):
        if not objeto_id:
            return ''
        modelo_map = {
            'producto': (Producto, self._format_producto),
            'categoria': (Categoria, self._format_nombre_basico),
            'proveedor': (Proveedor, self._format_proveedor),
            'cliente': (Cliente, self._format_cliente),
            'usuario': (Usuario, self._format_usuario),
            'mecanico': (Mecanico, self._format_nombre_basico),
            'moto': (Moto, self._format_moto),
            'orden-taller': (OrdenTaller, self._format_orden_taller),
            'movimiento': (MovimientoInventario, self._format_movimiento),
            'venta': (Venta, self._format_venta),
        }
        if modelo_slug not in modelo_map:
            return ''
        model_cls, formatter = modelo_map[modelo_slug]
        try:
            instance = model_cls.objects.filter(pk=objeto_id).first()
        except (ValueError, TypeError):
            return ''
        if not instance:
            return ''
        data = {}
        if hasattr(instance, 'nombre'):
            data['nombre'] = instance.nombre
        if hasattr(instance, 'codigo'):
            data['codigo'] = instance.codigo
        if hasattr(instance, 'nit'):
            data['nit'] = instance.nit
        if hasattr(instance, 'numero_documento'):
            data['numero_documento'] = instance.numero_documento
        if hasattr(instance, 'username'):
            data['username'] = instance.username
        if hasattr(instance, 'email'):
            data['email'] = instance.email
        if hasattr(instance, 'placa'):
            data['placa'] = instance.placa
        if hasattr(instance, 'marca'):
            data['marca'] = instance.marca
        if hasattr(instance, 'modelo'):
            data['modelo'] = instance.modelo
        if hasattr(instance, 'moto') and instance.moto:
            data['moto_placa'] = instance.moto.placa
            data['moto_marca'] = instance.moto.marca
            data['moto_modelo'] = instance.moto.modelo
        if hasattr(instance, 'mecanico') and instance.mecanico:
            data['mecanico_nombre'] = instance.mecanico.nombre
        if hasattr(instance, 'producto') and instance.producto:
            data['producto_nombre'] = instance.producto.nombre
        if hasattr(instance, 'tipo'):
            data['tipo_display'] = instance.get_tipo_display()
        if hasattr(instance, 'cantidad'):
            data['cantidad'] = instance.cantidad
        if hasattr(instance, 'numero_comprobante'):
            data['numero_comprobante'] = instance.numero_comprobante
        if hasattr(instance, 'cliente') and instance.cliente:
            data['cliente_nombre'] = instance.cliente.nombre
        return formatter(data, {})

    def _humanize_modelo(self, modelo):
        if not modelo:
            return ''
        etiquetas = {
            'producto': 'producto',
            'categoria': 'categoría',
            'proveedor': 'proveedor',
            'cliente': 'cliente',
            'usuario': 'usuario',
            'mecanico': 'mecánico',
            'moto': 'moto',
            'orden-taller': 'orden de taller',
            'movimiento': 'movimiento de inventario',
            'venta': 'venta',
            'impuesto': 'impuesto',
            'configuracion-empresa': 'configuración de empresa',
            'configuracion-facturacion': 'configuración de facturación',
        }
        if modelo in etiquetas:
            return etiquetas[modelo]
        return (
            modelo.replace('_', ' ')
            .replace('-', ' ')
            .replace('api:', '')
            .replace('viewset', '')
            .strip()
        )
