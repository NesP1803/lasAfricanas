from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models import Cliente, Venta, DetalleVenta, VentaAnulada
from .serializers import (
    ClienteSerializer,
    VentaListSerializer,
    VentaDetailSerializer,
    VentaCreateSerializer,
    VentaAnuladaSerializer
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
    queryset = Venta.objects.select_related(
        'cliente', 'vendedor'
    ).prefetch_related('detalles').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo_comprobante', 'estado', 'vendedor', 'cliente']
    search_fields = ['numero_comprobante', 'cliente__nombre', 'cliente__numero_documento']
    ordering_fields = ['fecha', 'total']
    ordering = ['-fecha']
    
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
        devuelve_inventario = request.data.get('devuelve_inventario', True)
        
        if not motivo:
            return Response(
                {'error': 'Debe proporcionar el motivo de anulación'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear registro de anulación
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
        
        if fecha_inicio:
            ventas = ventas.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            ventas = ventas.filter(fecha__lte=fecha_fin)
        
        stats = ventas.aggregate(
            total_ventas=Count('id'),
            total_facturado=Sum('total'),
            total_cotizaciones=Count('id', filter=Q(tipo_comprobante='COTIZACION')),
            total_remisiones=Count('id', filter=Q(tipo_comprobante='REMISION')),
            total_facturas=Count('id', filter=Q(tipo_comprobante='FACTURA')),
            total_facturas_valor=Sum('total', filter=Q(tipo_comprobante='FACTURA')),
            total_remisiones_valor=Sum('total', filter=Q(tipo_comprobante='REMISION')),
        )
        
        return Response(stats)
