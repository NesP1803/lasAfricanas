from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models import Mecanico, ServicioMoto, RepuestoAsignado, ConsumoRepuesto
from .serializers import (
    MecanicoSerializer,
    ServicioMotoListSerializer,
    ServicioMotoDetailSerializer,
    ServicioMotoCreateSerializer,
    RepuestoAsignadoSerializer,
    ConsumoRepuestoSerializer
)


class MecanicoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar mecánicos"""
    queryset = Mecanico.objects.filter(is_active=True).select_related('usuario')
    serializer_class = MecanicoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
        'especialidad'
    ]
    ordering_fields = ['created_at']
    ordering = ['usuario__first_name']
    
    @action(detail=True, methods=['get'])
    def repuestos(self, request, pk=None):
        """
        Retorna los repuestos asignados a un mecánico.
        
        GET /api/mecanicos/{id}/repuestos/
        """
        mecanico = self.get_object()
        repuestos = RepuestoAsignado.objects.filter(
            mecanico=mecanico,
            is_active=True
        ).select_related('producto')
        
        serializer = RepuestoAsignadoSerializer(repuestos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def servicios_activos(self, request, pk=None):
        """
        Retorna los servicios activos de un mecánico.
        
        GET /api/mecanicos/{id}/servicios_activos/
        """
        mecanico = self.get_object()
        servicios = ServicioMoto.objects.filter(
            mecanico=mecanico,
            estado__in=['INGRESADO', 'EN_DIAGNOSTICO', 'EN_REPARACION', 'COTIZADO', 'APROBADO']
        ).select_related('cliente')
        
        serializer = ServicioMotoListSerializer(servicios, many=True)
        return Response(serializer.data)


class ServicioMotoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar servicios de motos"""
    queryset = ServicioMoto.objects.select_related(
        'cliente', 'mecanico__usuario', 'recibido_por'
    ).prefetch_related('consumos_repuestos').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'mecanico', 'cliente']
    search_fields = [
        'numero_servicio',
        'placa',
        'marca',
        'modelo',
        'cliente__nombre',
        'cliente__numero_documento'
    ]
    ordering_fields = ['fecha_ingreso', 'fecha_estimada_entrega', 'total']
    ordering = ['-fecha_ingreso']
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción"""
        if self.action == 'list':
            return ServicioMotoListSerializer
        elif self.action == 'create':
            return ServicioMotoCreateSerializer
        return ServicioMotoDetailSerializer
    
    @action(detail=False, methods=['get'])
    def buscar_por_placa(self, request):
        """
        Busca servicios por placa.
        
        GET /api/servicios/buscar_por_placa/?placa=ABC123
        """
        placa = request.query_params.get('placa', '').upper().strip()
        if not placa:
            return Response(
                {'error': 'Debe proporcionar el parámetro placa'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        servicios = self.get_queryset().filter(placa__icontains=placa)
        serializer = ServicioMotoListSerializer(servicios, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_mecanico(self, request):
        """
        Retorna servicios de un mecánico específico.
        
        GET /api/servicios/por_mecanico/?mecanico_id=1&estado=EN_REPARACION
        """
        mecanico_id = request.query_params.get('mecanico_id')
        estado = request.query_params.get('estado')
        
        if not mecanico_id:
            return Response(
                {'error': 'Debe proporcionar el parámetro mecanico_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        servicios = self.get_queryset().filter(mecanico_id=mecanico_id)
        
        if estado:
            servicios = servicios.filter(estado=estado)
        
        serializer = ServicioMotoListSerializer(servicios, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def agregar_repuesto(self, request, pk=None):
        """
        Agrega un repuesto consumido al servicio.
        
        POST /api/servicios/{id}/agregar_repuesto/
        Body: {
            "producto_id": 1,
            "cantidad": 2,
            "precio_unitario": 15000,
            "descuento": 0
        }
        """
        servicio = self.get_object()
        
        if servicio.estado in ['ENTREGADO', 'CANCELADO']:
            return Response(
                {'error': 'No se pueden agregar repuestos a un servicio entregado o cancelado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        producto_id = request.data.get('producto_id')
        cantidad = request.data.get('cantidad')
        precio_unitario = request.data.get('precio_unitario')
        descuento = request.data.get('descuento', 0)
        
        if not all([producto_id, cantidad, precio_unitario]):
            return Response(
                {'error': 'Debe proporcionar producto_id, cantidad y precio_unitario'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.inventario.models import Producto
        
        try:
            producto = Producto.objects.get(id=producto_id, is_active=True)
        except Producto.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Crear consumo
        consumo = ConsumoRepuesto.objects.create(
            servicio=servicio,
            producto=producto,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            descuento=descuento,
            registrado_por=request.user
        )
        
        serializer = ConsumoRepuestoSerializer(consumo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """
        Cambia el estado del servicio.
        
        POST /api/servicios/{id}/cambiar_estado/
        Body: {
            "nuevo_estado": "EN_REPARACION",
            "observaciones": "Iniciando reparación"
        }
        """
        servicio = self.get_object()
        nuevo_estado = request.data.get('nuevo_estado')
        observaciones = request.data.get('observaciones', '')
        
        if not nuevo_estado:
            return Response(
                {'error': 'Debe proporcionar el nuevo_estado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        estados_validos = [choice[0] for choice in ServicioMoto.ESTADO]
        if nuevo_estado not in estados_validos:
            return Response(
                {'error': f'Estado inválido. Debe ser uno de: {", ".join(estados_validos)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        servicio.estado = nuevo_estado
        
        if observaciones:
            servicio.trabajo_realizado += f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {observaciones}"
        
        servicio.save()
        
        serializer = ServicioMotoDetailSerializer(servicio)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def facturar(self, request, pk=None):
        """
        Genera una factura para el servicio.
        
        POST /api/servicios/{id}/facturar/
        Body: {
            "tipo_comprobante": "FACTURA",
            "medio_pago": "EFECTIVO",
            "efectivo_recibido": 50000
        }
        """
        servicio = self.get_object()
        
        puede_facturar, mensaje = servicio.puede_facturar()
        if not puede_facturar:
            return Response(
                {'error': mensaje},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.ventas.models import Venta, DetalleVenta
        
        tipo_comprobante = request.data.get('tipo_comprobante', 'FACTURA')
        medio_pago = request.data.get('medio_pago', 'EFECTIVO')
        efectivo_recibido = request.data.get('efectivo_recibido', servicio.total)
        
        # Crear venta
        venta = Venta.objects.create(
            tipo_comprobante=tipo_comprobante,
            cliente=servicio.cliente,
            vendedor=request.user,
            subtotal=servicio.total,
            descuento_porcentaje=0,
            descuento_valor=0,
            iva=0,
            total=servicio.total,
            medio_pago=medio_pago,
            efectivo_recibido=efectivo_recibido,
            cambio=max(0, efectivo_recibido - servicio.total),
            observaciones=f"Servicio de taller {servicio.numero_servicio} - {servicio.placa}"
        )
        
        # Agregar mano de obra como detalle
        if servicio.costo_mano_obra > 0:
            DetalleVenta.objects.create(
                venta=venta,
                producto_id=None,  # Servicio sin producto específico
                cantidad=1,
                precio_unitario=servicio.costo_mano_obra,
                descuento_unitario=0,
                iva_porcentaje=0,
                subtotal=servicio.costo_mano_obra,
                total=servicio.costo_mano_obra,
                afecto_inventario=False
            )
        
        # Agregar repuestos como detalles
        for consumo in servicio.consumos_repuestos.filter(is_active=True):
            DetalleVenta.objects.create(
                venta=venta,
                producto=consumo.producto,
                cantidad=consumo.cantidad,
                precio_unitario=consumo.precio_unitario,
                descuento_unitario=consumo.descuento,
                iva_porcentaje=consumo.producto.iva_porcentaje,
                subtotal=consumo.subtotal,
                total=consumo.subtotal,
                afecto_inventario=False  # Ya se descontó cuando se consumió
            )
        
        # Asociar venta al servicio
        servicio.venta = venta
        servicio.save()
        
        from apps.ventas.serializers import VentaDetailSerializer
        serializer = VentaDetailSerializer(venta)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def historial_por_placa(self, request):
        """
        Retorna el historial completo de servicios para una placa.

        GET /api/servicios/historial_por_placa/?placa=ABC123
        """
        placa = request.query_params.get('placa', '').upper().strip()
        if not placa:
            return Response(
                {'error': 'Debe proporcionar el parámetro placa'},
                status=status.HTTP_400_BAD_REQUEST
            )

        servicios = self.get_queryset().filter(placa__iexact=placa).order_by('-fecha_ingreso')
        serializer = ServicioMotoDetailSerializer(servicios, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Retorna estadísticas generales del taller.

        GET /api/servicios/estadisticas/
        """
        from datetime import datetime, timedelta

        # Fecha de inicio (último mes)
        fecha_inicio = timezone.now() - timedelta(days=30)

        # Servicios totales
        servicios_totales = self.get_queryset().count()

        # Servicios por estado
        servicios_por_estado = {}
        for estado_code, estado_name in ServicioMoto.ESTADO:
            count = self.get_queryset().filter(estado=estado_code).count()
            servicios_por_estado[estado_code] = {
                'nombre': estado_name,
                'cantidad': count
            }

        # Servicios del último mes
        servicios_mes = self.get_queryset().filter(
            fecha_ingreso__gte=fecha_inicio
        ).count()

        # Facturación del último mes
        facturacion_mes = self.get_queryset().filter(
            fecha_ingreso__gte=fecha_inicio,
            estado='ENTREGADO'
        ).aggregate(total=Sum('total'))['total'] or 0

        # Servicios pendientes (no entregados ni cancelados)
        servicios_pendientes = self.get_queryset().exclude(
            estado__in=['ENTREGADO', 'CANCELADO']
        ).count()

        # Tiempo promedio de entrega (en días)
        from django.db.models import Avg, ExpressionWrapper, F, DurationField

        servicios_entregados = self.get_queryset().filter(
            estado='ENTREGADO',
            fecha_entrega_real__isnull=False
        )

        if servicios_entregados.exists():
            tiempo_promedio = servicios_entregados.annotate(
                duracion=ExpressionWrapper(
                    F('fecha_entrega_real') - F('fecha_ingreso'),
                    output_field=DurationField()
                )
            ).aggregate(promedio=Avg('duracion'))['promedio']

            tiempo_promedio_dias = tiempo_promedio.days if tiempo_promedio else 0
        else:
            tiempo_promedio_dias = 0

        return Response({
            'servicios_totales': servicios_totales,
            'servicios_por_estado': servicios_por_estado,
            'servicios_ultimo_mes': servicios_mes,
            'facturacion_ultimo_mes': facturacion_mes,
            'servicios_pendientes': servicios_pendientes,
            'tiempo_promedio_entrega_dias': tiempo_promedio_dias
        })


class RepuestoAsignadoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar repuestos asignados a mecánicos"""
    queryset = RepuestoAsignado.objects.filter(is_active=True).select_related(
        'mecanico__usuario', 'producto'
    )
    serializer_class = RepuestoAsignadoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['mecanico']
    search_fields = ['producto__codigo', 'producto__nombre']


class ConsumoRepuestoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para consultar consumos de repuestos (solo lectura)"""
    queryset = ConsumoRepuesto.objects.select_related(
        'servicio', 'producto', 'registrado_por'
    ).all()
    serializer_class = ConsumoRepuestoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['servicio', 'descontado_de_mecanico']
    search_fields = ['servicio__numero_servicio', 'producto__codigo', 'producto__nombre']
    ordering = ['-created_at']