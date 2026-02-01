from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, time

from .models import Cliente, Venta, DetalleVenta, SolicitudDescuento, VentaAnulada, RemisionAnulada, Caja
from .serializers import (
    ClienteSerializer,
    VentaListSerializer,
    VentaDetailSerializer,
    VentaCreateSerializer,
    VentaAnuladaSerializer,
    SolicitudDescuentoSerializer,
    CajaSerializer,
    VentaPendienteCajaSerializer,
    ProcesarPagoSerializer,
    EnviarACajaSerializer,
)


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
    filterset_fields = ['tipo_comprobante', 'estado', 'estado_pago', 'vendedor', 'cliente', 'caja_destino', 'cajero']
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
            'cliente', 'vendedor', 'cajero', 'caja_destino'
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
        elif self.action == 'create':
            return VentaCreateSerializer
        return VentaDetailSerializer
    
    @action(detail=False, methods=['get'])
    def remisiones_pendientes(self, request):
        """
        Retorna remisiones que aún no se han convertido en facturas.
        Útil para el reporte de "Remisiones por facturar".
        """
        remisiones = self.get_queryset().filter(
            tipo_comprobante='REMISION',
            estado='CONFIRMADA',
            facturas_generadas__isnull=True  # No tiene factura asociada
        )

        serializer = VentaListSerializer(remisiones, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pendientes_caja(self, request):
        """
        Retorna ventas pendientes de cobro en caja.
        Filtra por la caja del usuario si es cajero.

        GET /api/ventas/pendientes_caja/
        GET /api/ventas/pendientes_caja/?caja=1
        """
        ventas = self.get_queryset().filter(
            estado_pago='PENDIENTE_CAJA',
            estado='CONFIRMADA'
        )

        # Si el usuario es cajero, filtrar por su caja asignada
        caja_id = request.query_params.get('caja')
        if caja_id:
            ventas = ventas.filter(caja_destino_id=caja_id)
        elif hasattr(request.user, 'caja') and request.user.caja:
            ventas = ventas.filter(caja_destino=request.user.caja)

        serializer = VentaPendienteCajaSerializer(ventas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def enviar_a_caja(self, request, pk=None):
        """
        Envía una venta a caja para procesamiento de pago.

        POST /api/ventas/{id}/enviar_a_caja/
        Body: {
            "caja_destino": 1
        }
        """
        venta = self.get_object()

        if venta.tipo_comprobante == 'COTIZACION':
            return Response(
                {'error': 'Las cotizaciones no se pueden enviar a caja'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if venta.estado_pago == 'PAGADO':
            return Response(
                {'error': 'Esta venta ya está pagada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = EnviarACajaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        caja = serializer.validated_data['caja_destino']
        venta.enviar_a_caja(caja)

        return Response(
            VentaDetailSerializer(venta).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def procesar_pago(self, request, pk=None):
        """
        Procesa el pago de una venta pendiente en caja.

        POST /api/ventas/{id}/procesar_pago/
        Body: {
            "medio_pago": "EFECTIVO",
            "efectivo_recibido": 150000,
            "observaciones": ""
        }
        """
        venta = self.get_object()

        # Verificar que el usuario puede procesar pagos
        if not request.user.puede_procesar_pagos:
            return Response(
                {'error': 'No tiene permisos para procesar pagos'},
                status=status.HTTP_403_FORBIDDEN
            )

        if venta.estado_pago == 'PAGADO':
            return Response(
                {'error': 'Esta venta ya está pagada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ProcesarPagoSerializer(
            data=request.data,
            context={'venta': venta}
        )
        serializer.is_valid(raise_exception=True)

        try:
            venta.procesar_pago(
                cajero=request.user,
                medio_pago=serializer.validated_data['medio_pago'],
                efectivo_recibido=serializer.validated_data.get('efectivo_recibido', 0)
            )

            # Agregar observaciones si se proporcionaron
            observaciones = serializer.validated_data.get('observaciones', '')
            if observaciones:
                venta.observaciones = f"{venta.observaciones}\n[Caja] {observaciones}".strip()
                venta.save()

            return Response(
                VentaDetailSerializer(venta).data,
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

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
        
        if remision.estado != 'CONFIRMADA':
            return Response(
                {'error': 'Solo se pueden facturar remisiones confirmadas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            factura = remision.convertir_a_factura()
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
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Retorna estadísticas de ventas.
        
        GET /api/ventas/estadisticas/?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        
        ventas = self.get_queryset().filter(estado='CONFIRMADA')
        
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


class CajaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar cajas"""
    queryset = Caja.objects.all()
    serializer_class = CajaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['nombre', 'descripcion', 'ubicacion']
    ordering_fields = ['nombre', 'created_at']
    ordering = ['nombre']

    @action(detail=True, methods=['get'])
    def ventas_pendientes(self, request, pk=None):
        """
        Retorna las ventas pendientes de cobro para esta caja.

        GET /api/cajas/{id}/ventas_pendientes/
        """
        caja = self.get_object()
        ventas = Venta.objects.filter(
            caja_destino=caja,
            estado_pago='PENDIENTE_CAJA',
            estado='CONFIRMADA'
        ).select_related('cliente', 'vendedor').prefetch_related('detalles')

        serializer = VentaPendienteCajaSerializer(ventas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        """
        Retorna estadísticas de la caja.

        GET /api/cajas/{id}/estadisticas/
        """
        caja = self.get_object()

        # Ventas pendientes
        pendientes = Venta.objects.filter(
            caja_destino=caja,
            estado_pago='PENDIENTE_CAJA',
            estado='CONFIRMADA'
        ).aggregate(
            cantidad=Count('id'),
            total=Sum('total')
        )

        # Ventas cobradas hoy
        hoy = timezone.now().date()
        tz = timezone.get_current_timezone()
        inicio_hoy = timezone.make_aware(
            datetime.combine(hoy, time.min),
            tz
        )
        fin_hoy = timezone.make_aware(
            datetime.combine(hoy, time.max),
            tz
        )

        cobradas_hoy = Venta.objects.filter(
            caja_destino=caja,
            estado_pago='PAGADO',
            fecha_cobro__gte=inicio_hoy,
            fecha_cobro__lte=fin_hoy
        ).aggregate(
            cantidad=Count('id'),
            total=Sum('total'),
            efectivo=Sum('total', filter=Q(medio_pago='EFECTIVO')),
            transferencia=Sum('total', filter=Q(medio_pago='TRANSFERENCIA')),
            tarjeta=Sum('total', filter=Q(medio_pago='TARJETA')),
            credito=Sum('total', filter=Q(medio_pago='CREDITO')),
        )

        return Response({
            'pendientes': {
                'cantidad': pendientes['cantidad'] or 0,
                'total': pendientes['total'] or 0
            },
            'cobradas_hoy': {
                'cantidad': cobradas_hoy['cantidad'] or 0,
                'total': cobradas_hoy['total'] or 0,
                'por_medio_pago': {
                    'efectivo': cobradas_hoy['efectivo'] or 0,
                    'transferencia': cobradas_hoy['transferencia'] or 0,
                    'tarjeta': cobradas_hoy['tarjeta'] or 0,
                    'credito': cobradas_hoy['credito'] or 0,
                }
            },
            'cajeros_asignados': caja.cajeros_asignados.count()
        })
