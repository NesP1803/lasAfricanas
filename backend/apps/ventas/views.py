from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.db import transaction
from datetime import datetime, time
from decimal import Decimal

from .models import Cliente, Venta, DetalleVenta, SolicitudDescuento, VentaAnulada, RemisionAnulada
from .serializers import (
    ClienteSerializer,
    VentaListSerializer,
    VentaDetailSerializer,
    VentaCreateSerializer,
    VentaAnuladaSerializer,
    SolicitudDescuentoSerializer,
)


def _is_admin(user):
    return bool(
        user
        and (
            user.is_superuser
            or user.is_staff
            or getattr(user, 'tipo_usuario', None) == 'ADMIN'
        )
    )


def _is_caja(user):
    return bool(
        _is_admin(user)
        or getattr(user, 'es_cajero', False)
        or user.has_perm('ventas.caja_facturar')
    )


def _validar_detalles_venta(venta):
    detalles = list(venta.detalles.select_related('producto'))
    if not detalles:
        raise ValidationError('La venta no tiene detalles para facturar.')

    subtotal = sum((detalle.subtotal for detalle in detalles), Decimal('0.00'))
    total = sum((detalle.total for detalle in detalles), Decimal('0.00'))

    normalized_subtotal = Decimal(subtotal).quantize(Decimal('0.01'))
    normalized_total = Decimal(total).quantize(Decimal('0.01'))

    if normalized_subtotal != Decimal(venta.subtotal).quantize(Decimal('0.01')):
        raise ValidationError('El subtotal no coincide con los detalles.')

    if normalized_total != Decimal(venta.total).quantize(Decimal('0.01')):
        raise ValidationError('El total no coincide con los detalles.')

    return detalles


def _registrar_salida_inventario(venta, user, detalles=None):
    if not venta.afecta_inventario:
        return

    from apps.inventario.models import MovimientoInventario, Producto

    detalles = detalles or list(venta.detalles.select_related('producto'))
    productos_ids = [detalle.producto_id for detalle in detalles if detalle.afecto_inventario]
    if productos_ids:
        productos = {
            producto.id: producto
            for producto in Producto.objects.select_for_update().filter(id__in=productos_ids)
        }
    else:
        productos = {}

    for detalle in detalles:
        if not detalle.afecto_inventario:
            continue
        producto = productos.get(detalle.producto_id) or detalle.producto
        stock_anterior = producto.stock
        stock_nuevo = stock_anterior - detalle.cantidad
        if stock_nuevo < 0:
            raise ValidationError(f'Stock insuficiente para {producto.nombre}.')
        MovimientoInventario.objects.create(
            producto=producto,
            tipo='SALIDA',
            cantidad=-abs(detalle.cantidad),
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo,
            costo_unitario=detalle.precio_unitario,
            usuario=user,
            referencia=venta.numero_comprobante or f'VENTA-{venta.id}',
            observaciones='Facturación en caja',
        )


def _facturar_venta(venta, user):
    if venta.estado == 'FACTURADA':
        raise ValidationError('La venta ya está facturada.')
    if venta.estado not in {'BORRADOR', 'ENVIADA_A_CAJA'}:
        raise ValidationError('La venta no se puede facturar en este estado.')

    detalles = _validar_detalles_venta(venta)

    venta.estado = 'FACTURADA'
    venta.facturada_por = user
    venta.facturada_at = timezone.now()
    venta.save()

    _registrar_salida_inventario(venta, user, detalles=detalles)


class ClienteViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar clientes"""
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo_documento', 'ciudad', 'is_active']
    search_fields = ['numero_documento', 'nombre', 'telefono', 'email']
    ordering_fields = ['nombre', 'created_at']
    ordering = ['nombre']
    
    @action(detail=False, methods=['get'])
    def buscar_por_documento(self, request):
        """
        Busca cliente por número de documento.
        
        GET /api/clientes/buscar_por_documento/?documento=222222
        """
        documento = request.query_params.get('documento', None)
        if not documento:
            return Response(
                {'error': 'Debe proporcionar el parámetro documento'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cliente = Cliente.objects.get(numero_documento=documento, is_active=True)
            serializer = self.get_serializer(cliente)
            return Response(serializer.data)
        except Cliente.DoesNotExist:
            return Response(
                {'error': 'Cliente no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class VentaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar ventas"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo_comprobante', 'estado', 'vendedor', 'cliente']
    search_fields = ['numero_comprobante', 'cliente__nombre', 'cliente__numero_documento']
    ordering_fields = ['fecha', 'total']
    ordering = ['-fecha']

    @staticmethod
    def _get_fecha_range(fecha_inicio, fecha_fin):
        tz = timezone.get_current_timezone()
        inicio_dt = fin_dt = None
        if fecha_inicio:
            inicio_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            inicio_dt = timezone.make_aware(
                datetime.combine(inicio_date, time.min),
                tz
            )
        if fecha_fin:
            fin_date = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            fin_dt = timezone.make_aware(
                datetime.combine(fin_date, time.max),
                tz
            )
        return inicio_dt, fin_dt

    def get_queryset(self):
        queryset = Venta.objects.select_related(
            'cliente', 'vendedor'
        ).prefetch_related('detalles').all()
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        inicio_dt, fin_dt = self._get_fecha_range(fecha_inicio, fecha_fin)
        if inicio_dt:
            queryset = queryset.filter(fecha__gte=inicio_dt)
        if fin_dt:
            queryset = queryset.filter(fecha__lte=fin_dt)
        return queryset
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción"""
        if self.action == 'list':
            return VentaListSerializer
        elif self.action in {'create', 'update', 'partial_update'}:
            return VentaCreateSerializer
        return VentaDetailSerializer

    def perform_create(self, serializer):
        user = self.request.user
        vendedor = serializer.validated_data.get('vendedor')
        if not _is_admin(user):
            vendedor = user
        tipo_comprobante = serializer.validated_data.get('tipo_comprobante')
        estado = 'BORRADOR' if tipo_comprobante == 'FACTURA' else 'FACTURADA'
        serializer.save(
            vendedor=vendedor or user,
            creada_por=user,
            estado=estado,
        )

    def create(self, request, *args, **kwargs):
        payload = request.data.copy()
        facturar_directo = bool(payload.pop('facturar_directo', False))
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.perform_create(serializer)
            venta = serializer.instance
            if facturar_directo and venta.tipo_comprobante == 'FACTURA':
                _facturar_venta(venta, request.user)
        detail_serializer = VentaDetailSerializer(venta, context=self.get_serializer_context())
        headers = self.get_success_headers(detail_serializer.data)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _puede_editar_venta(self, user, venta):
        """Verifica si el usuario puede editar la venta según su estado."""
        if _is_admin(user):
            return True
        if venta.estado == 'BORRADOR':
            return True
        # Cajeros pueden editar ventas enviadas a caja (para actualizar pago)
        if venta.estado == 'ENVIADA_A_CAJA' and _is_caja(user):
            return True
        return False

    def update(self, request, *args, **kwargs):
        venta = self.get_object()
        if not self._puede_editar_venta(request.user, venta):
            return Response(
                {'error': 'Solo se pueden editar ventas en borrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        venta = self.get_object()
        if not self._puede_editar_venta(request.user, venta):
            return Response(
                {'error': 'Solo se pueden editar ventas en borrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def remisiones_pendientes(self, request):
        """
        Retorna remisiones que aún no se han convertido en facturas.
        Útil para el reporte de "Remisiones por facturar".
        """
        remisiones = self.get_queryset().filter(
            tipo_comprobante='REMISION',
            estado='FACTURADA',
            facturas_generadas__isnull=True  # No tiene factura asociada
        )
        
        serializer = VentaListSerializer(remisiones, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['post'])
    def convertir_a_factura(self, request, pk=None):
        """
        Convierte una remisión en factura electrónica.
        
        POST /api/ventas/{id}/convertir_a_factura/
        """
        remision = self.get_object()
        
        if remision.tipo_comprobante != 'REMISION':
            return Response(
                {'error': 'Solo se pueden convertir remisiones a facturas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if remision.estado != 'FACTURADA':
            return Response(
                {'error': 'Solo se pueden facturar remisiones confirmadas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            factura = remision.convertir_a_factura()
            factura.estado = 'FACTURADA'
            factura.facturada_por = request.user
            factura.facturada_at = timezone.now()
            factura.save()
            serializer = VentaDetailSerializer(factura)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        """
        Anula una venta.
        
        POST /api/ventas/{id}/anular/
        Body: {
            "motivo": "DEVOLUCION_TOTAL",
            "descripcion": "Cliente devolvió la mercancía",
            "devuelve_inventario": true
        }
        """
        venta = self.get_object()
        
        if venta.estado == 'ANULADA':
            return Response(
                {'error': 'Esta venta ya está anulada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        motivo = request.data.get('motivo')
        descripcion = request.data.get('descripcion', '')
        devuelve_inventario = True
        
        if not motivo:
            return Response(
                {'error': 'Debe proporcionar el motivo de anulación'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear registro de anulación
        if venta.tipo_comprobante == 'REMISION':
            RemisionAnulada.objects.create(
                remision=venta,
                motivo=motivo,
                descripcion=descripcion,
                anulado_por=request.user,
                devuelve_inventario=devuelve_inventario
            )
        else:
            VentaAnulada.objects.create(
                venta=venta,
                motivo=motivo,
                descripcion=descripcion,
                anulado_por=request.user,
                devuelve_inventario=devuelve_inventario
            )
        
        # Cambiar estado de la venta
        venta.estado = 'ANULADA'
        venta.save()
        
        # Si devuelve inventario, restaurar stock
        if devuelve_inventario and venta.afecta_inventario:
            from apps.inventario.models import MovimientoInventario
            
            for detalle in venta.detalles.all():
                if detalle.afecto_inventario:
                    producto = detalle.producto
                    stock_anterior = producto.stock
                    stock_nuevo = stock_anterior + detalle.cantidad
                    
                    MovimientoInventario.objects.create(
                        producto=producto,
                        tipo='DEVOLUCION',
                        cantidad=detalle.cantidad,
                        stock_anterior=stock_anterior,
                        stock_nuevo=stock_nuevo,
                        costo_unitario=detalle.precio_unitario,
                        usuario=request.user,
                        referencia=f"Anulación {venta.numero_comprobante}",
                        observaciones=f"Devolución por anulación: {descripcion}"
                    )
                    
                    producto.stock = stock_nuevo
                    producto.save()
        
        serializer = VentaDetailSerializer(venta)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='enviar-a-caja')
    def enviar_a_caja(self, request, pk=None):
        venta = self.get_object()

        if venta.estado != 'BORRADOR':
            return Response(
                {'error': 'Solo se pueden enviar a caja ventas en borrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        venta.estado = 'ENVIADA_A_CAJA'
        venta.enviada_a_caja_por = request.user
        venta.enviada_a_caja_at = timezone.now()
        venta.save(
            update_fields=[
                'estado',
                'enviada_a_caja_por',
                'enviada_a_caja_at',
                'updated_at',
            ]
        )

        serializer = VentaDetailSerializer(venta)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Retorna estadísticas de ventas.
        
        GET /api/ventas/estadisticas/?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        
        ventas = self.get_queryset().filter(estado='FACTURADA')
        
        inicio_dt, fin_dt = self._get_fecha_range(fecha_inicio, fecha_fin)
        if inicio_dt:
            ventas = ventas.filter(fecha__gte=inicio_dt)
        if fin_dt:
            ventas = ventas.filter(fecha__lte=fin_dt)
        
        stats = ventas.aggregate(
            total_ventas=Count('id'),
            total_facturado=Sum('total'),
            total_cotizaciones=Count('id', filter=Q(tipo_comprobante='COTIZACION')),
            total_remisiones=Count('id', filter=Q(tipo_comprobante='REMISION')),
            total_facturas=Count('id', filter=Q(tipo_comprobante='FACTURA')),
            total_facturas_valor=Sum('total', filter=Q(tipo_comprobante='FACTURA')),
            total_remisiones_valor=Sum('total', filter=Q(tipo_comprobante='REMISION')),
        )

        ventas_por_usuario = (
            ventas.values(
                'vendedor_id',
                'vendedor__first_name',
                'vendedor__last_name',
                'vendedor__username',
            )
            .annotate(
                total_facturas=Count('id', filter=Q(tipo_comprobante='FACTURA')),
                total_remisiones=Count('id', filter=Q(tipo_comprobante='REMISION')),
            )
            .order_by('vendedor__first_name', 'vendedor__last_name', 'vendedor__username')
        )

        facturas_por_usuario = []
        remisiones_por_usuario = []
        for item in ventas_por_usuario:
            nombre = f"{item['vendedor__first_name']} {item['vendedor__last_name']}".strip()
            if not nombre:
                nombre = item['vendedor__username']
            if item['total_facturas'] > 0:
                facturas_por_usuario.append(
                    {'usuario': nombre, 'cuentas': item['total_facturas']}
                )
            if item['total_remisiones'] > 0:
                remisiones_por_usuario.append(
                    {'usuario': nombre, 'cuentas': item['total_remisiones']}
                )

        stats['facturas_por_usuario'] = facturas_por_usuario
        stats['remisiones_por_usuario'] = remisiones_por_usuario
        
        return Response(stats)


class CajaViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = VentaDetailSerializer

    def get_queryset(self):
        return Venta.objects.select_related(
            'cliente',
            'vendedor',
            'facturada_por',
            'enviada_a_caja_por',
        ).prefetch_related('detalles', 'detalles__producto')

    def _require_caja(self, request):
        if not _is_caja(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _validar_para_facturar(self, venta):
        if venta.estado != 'ENVIADA_A_CAJA':
            raise ValidationError('La venta no está enviada a caja.')

        _validar_detalles_venta(venta)

    @action(detail=False, methods=['get'], url_path='pendientes')
    def pendientes(self, request):
        permission_response = self._require_caja(request)
        if permission_response:
            return permission_response

        # Solo mostrar ventas enviadas a caja HOY
        hoy = timezone.localdate()
        ventas = self.get_queryset().filter(
            estado='ENVIADA_A_CAJA',
            enviada_a_caja_at__date=hoy,
        ).order_by(
            'enviada_a_caja_at',
            'fecha',
            'id',
        )
        serializer = VentaListSerializer(ventas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def facturar(self, request, pk=None):
        permission_response = self._require_caja(request)
        if permission_response:
            return permission_response

        with transaction.atomic():
            venta = (
                Venta.objects.select_for_update()
                .select_related('cliente', 'vendedor')
                .prefetch_related('detalles', 'detalles__producto')
                .get(pk=pk)
            )
            try:
                self._validar_para_facturar(venta)
                _facturar_venta(venta, request.user)
            except ValidationError as error:
                return Response({'error': error.detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VentaDetailSerializer(venta)
        return Response(serializer.data)


class SolicitudDescuentoViewSet(viewsets.ModelViewSet):
    """ViewSet para solicitudes de descuento"""
    serializer_class = SolicitudDescuentoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'vendedor', 'aprobador']
    search_fields = ['vendedor__username', 'aprobador__username']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff or getattr(user, 'tipo_usuario', None) == 'ADMIN':
            return SolicitudDescuento.objects.filter(aprobador=user)
        return SolicitudDescuento.objects.filter(vendedor=user)

    def perform_create(self, serializer):
        aprobador = serializer.validated_data.get('aprobador')
        if not aprobador or not (
            aprobador.is_superuser
            or aprobador.is_staff
            or getattr(aprobador, 'tipo_usuario', None) == 'ADMIN'
        ):
            raise ValidationError({'aprobador': 'Aprobador inválido.'})
        serializer.save(vendedor=self.request.user)

    def update(self, request, *args, **kwargs):
        if request.user != self.get_object().aprobador:
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if request.user != self.get_object().aprobador:
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)
