from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.inventario.models import Producto
from apps.ventas.models import DetalleVenta, Venta
from .models import Mecanico, Moto, OrdenTaller, OrdenRepuesto
from .serializers import MecanicoSerializer, MotoSerializer, OrdenTallerSerializer


class MecanicoViewSet(viewsets.ModelViewSet):
    queryset = Mecanico.objects.all()
    serializer_class = MecanicoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['nombre', 'telefono', 'email', 'ciudad']
    ordering_fields = ['nombre', 'created_at']
    ordering = ['nombre']


class MotoViewSet(viewsets.ModelViewSet):
    queryset = Moto.objects.filter(is_active=True).select_related('mecanico', 'proveedor', 'cliente')
    serializer_class = MotoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['mecanico', 'proveedor', 'cliente']
    search_fields = ['placa', 'marca', 'modelo', 'cliente__nombre']
    ordering_fields = ['placa', 'marca', 'created_at']
    ordering = ['placa']


class OrdenTallerViewSet(viewsets.ModelViewSet):
    queryset = OrdenTaller.objects.select_related('moto', 'mecanico', 'venta').prefetch_related('repuestos__producto')
    serializer_class = OrdenTallerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'mecanico', 'moto']
    search_fields = ['moto__placa', 'moto__marca', 'mecanico__nombre']
    ordering_fields = ['created_at', 'estado']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def agregar_repuesto(self, request, pk=None):
        orden = self.get_object()
        producto_id = request.data.get('producto')
        cantidad = request.data.get('cantidad', 1)

        if not producto_id:
            return Response({'error': 'Debe proporcionar el producto'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            producto = Producto.objects.get(pk=producto_id, is_active=True)
        except Producto.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        try:
            cantidad = int(cantidad)
            if cantidad <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'error': 'Cantidad inválida'}, status=status.HTTP_400_BAD_REQUEST)

        repuesto, created = OrdenRepuesto.objects.get_or_create(
            orden=orden,
            producto=producto,
            defaults={
                'cantidad': cantidad,
                'precio_unitario': producto.precio_venta,
                'subtotal': Decimal('0'),
            }
        )
        if not created:
            repuesto.cantidad += cantidad
            repuesto.precio_unitario = producto.precio_venta
            repuesto.save()

        serializer = OrdenTallerSerializer(orden)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def quitar_repuesto(self, request, pk=None):
        orden = self.get_object()
        repuesto_id = request.data.get('repuesto_id')
        producto_id = request.data.get('producto')

        if repuesto_id:
            OrdenRepuesto.objects.filter(pk=repuesto_id, orden=orden).delete()
        elif producto_id:
            OrdenRepuesto.objects.filter(orden=orden, producto_id=producto_id).delete()
        else:
            return Response({'error': 'Debe indicar repuesto_id o producto'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrdenTallerSerializer(orden)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def facturar(self, request, pk=None):
        orden = self.get_object()
        if orden.estado == 'FACTURADO':
            return Response({'error': 'La orden ya está facturada'}, status=status.HTTP_400_BAD_REQUEST)

        if not orden.moto.cliente:
            return Response({'error': 'La moto no tiene cliente asignado'}, status=status.HTTP_400_BAD_REQUEST)

        tipo_comprobante = request.data.get('tipo_comprobante', 'REMISION')
        if tipo_comprobante not in ['REMISION', 'FACTURA']:
            return Response({'error': 'Tipo de comprobante inválido'}, status=status.HTTP_400_BAD_REQUEST)

        repuestos = orden.repuestos.select_related('producto').all()
        if not repuestos:
            return Response({'error': 'La orden no tiene repuestos asociados'}, status=status.HTTP_400_BAD_REQUEST)

        subtotal = Decimal('0')
        iva_total = Decimal('0')
        detalles = []

        for repuesto in repuestos:
            producto = repuesto.producto
            subtotal_item = Decimal(repuesto.cantidad) * Decimal(repuesto.precio_unitario)
            iva_porcentaje = Decimal(producto.iva_porcentaje)
            iva_item = (subtotal_item * iva_porcentaje) / Decimal('100')
            total_item = subtotal_item + iva_item

            subtotal += subtotal_item
            iva_total += iva_item

            detalles.append({
                'producto': producto,
                'cantidad': repuesto.cantidad,
                'precio_unitario': repuesto.precio_unitario,
                'descuento_unitario': Decimal('0'),
                'iva_porcentaje': iva_porcentaje,
                'subtotal': subtotal_item,
                'total': total_item,
            })

        total = subtotal + iva_total

        with transaction.atomic():
            venta = Venta.objects.create(
                tipo_comprobante=tipo_comprobante,
                cliente=orden.moto.cliente,
                vendedor=request.user,
                subtotal=subtotal,
                descuento_porcentaje=Decimal('0'),
                descuento_valor=Decimal('0'),
                iva=iva_total,
                total=total,
                medio_pago='EFECTIVO',
                efectivo_recibido=total,
                cambio=Decimal('0'),
                observaciones=f"Venta generada desde orden de taller {orden.id}",
            )

            for detalle in detalles:
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=detalle['producto'],
                    cantidad=detalle['cantidad'],
                    precio_unitario=detalle['precio_unitario'],
                    descuento_unitario=detalle['descuento_unitario'],
                    iva_porcentaje=detalle['iva_porcentaje'],
                    subtotal=detalle['subtotal'],
                    total=detalle['total'],
                )

            orden.estado = 'FACTURADO'
            orden.fecha_entrega = timezone.now()
            orden.venta = venta
            orden.save()

        serializer = OrdenTallerSerializer(orden)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
