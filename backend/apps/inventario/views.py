from django.db import models
from django.db.models import F, Sum
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import Categoria, Proveedor, Producto, MovimientoInventario, ProductoFavorito
from .serializers import (
    CategoriaSerializer,
    ProveedorSerializer,
    ProductoListSerializer,
    ProductoDetailSerializer,
    ProductoCreateUpdateSerializer,
    MovimientoInventarioSerializer,
    ProductoFavoritoSerializer,
)


class CategoriaViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar categorías.
    
    list: Listar todas las categorías
    create: Crear nueva categoría
    retrieve: Obtener detalle de categoría
    update: Actualizar categoría
    partial_update: Actualizar parcialmente
    destroy: Eliminar (soft delete)
    """
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre', 'orden', 'created_at']
    ordering = ['orden', 'nombre']
    
    @action(detail=False, methods=['get'])
    def activas(self, request):
        """Retorna solo categorías activas ordenadas"""
        categorias = self.get_queryset().filter(is_active=True).order_by('orden', 'nombre')
        serializer = self.get_serializer(categorias, many=True)
        return Response(serializer.data)


class ProveedorViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar proveedores"""
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['nombre', 'nit', 'contacto', 'ciudad']
    ordering_fields = ['nombre', 'ciudad', 'created_at']
    ordering = ['nombre']
    
    @action(detail=False, methods=['get'])
    def buscar_por_nit(self, request):
        """Busca proveedor por NIT"""
        nit = request.query_params.get('nit', None)
        if not nit:
            return Response(
                {'error': 'Debe proporcionar el parámetro nit'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            proveedor = Proveedor.objects.get(nit=nit, is_active=True)
            serializer = self.get_serializer(proveedor)
            return Response(serializer.data)
        except Proveedor.DoesNotExist:
            return Response(
                {'error': 'Proveedor no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class ProductoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar productos.
    Usa diferentes serializers según la acción.
    """
    queryset = Producto.objects.filter(is_active=True).select_related('categoria', 'proveedor')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['categoria', 'proveedor', 'es_servicio']
    search_fields = ['codigo', 'nombre', 'descripcion']
    ordering_fields = ['nombre', 'precio_venta', 'stock', 'created_at']
    ordering = ['nombre']

    def get_queryset(self):
        queryset = super().get_queryset()
        stock_estado = self.request.query_params.get('stock_estado')
        if stock_estado:
            normalized = stock_estado.strip().lower()
            if normalized == 'agotado':
                queryset = queryset.filter(stock__lte=0)
            elif normalized == 'bajo':
                queryset = queryset.filter(
                    Q(stock__gt=0) & Q(stock__lte=models.F('stock_minimo'))
                )
            elif normalized == 'ok':
                queryset = queryset.filter(stock__gt=models.F('stock_minimo'))
        return queryset
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción"""
        if self.action == 'list':
            return ProductoListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductoCreateUpdateSerializer
        return ProductoDetailSerializer
    
    @action(detail=False, methods=['get'])
    def buscar_por_codigo(self, request):
        """
        Busca un producto por su código exacto.
        Útil para lectores de código de barras.
        
        GET /api/productos/buscar_por_codigo/?codigo=069
        """
        codigo = request.query_params.get('codigo', None)
        if not codigo:
            return Response(
                {'error': 'Debe proporcionar el parámetro codigo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            producto = Producto.objects.select_related('categoria', 'proveedor').get(
                codigo=codigo,
                is_active=True
            )
            serializer = ProductoDetailSerializer(producto)
            return Response(serializer.data)
        except Producto.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def stock_bajo(self, request):
        """Retorna productos con stock bajo"""
        productos = self.get_queryset().filter(
            stock__lte=models.F('stock_minimo')
        ).order_by('stock')
        page = self.paginate_queryset(productos)
        if page is not None:
            serializer = ProductoListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ProductoListSerializer(productos, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Retorna estadísticas generales del inventario."""
        queryset = self.get_queryset()
        total = queryset.count()
        stock_bajo = queryset.filter(stock__lte=models.F('stock_minimo')).count()
        agotados = queryset.filter(stock__lte=0).count()
        valor_inventario = (
            queryset.aggregate(total=Sum(F('precio_costo') * F('stock')))['total'] or 0
        )
        return Response(
            {
                'total': total,
                'stock_bajo': stock_bajo,
                'agotados': agotados,
                'valor_inventario': valor_inventario,
            }
        )
    
    @action(detail=False, methods=['get'])
    def por_categoria(self, request):
        """
        Retorna productos de una categoría específica.
        
        GET /api/productos/por_categoria/?categoria_id=1
        """
        categoria_id = request.query_params.get('categoria_id', None)
        if not categoria_id:
            return Response(
                {'error': 'Debe proporcionar el parámetro categoria_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        productos = self.get_queryset().filter(categoria_id=categoria_id)
        serializer = ProductoListSerializer(productos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def ajustar_stock(self, request, pk=None):
        """
        Ajusta manualmente el stock de un producto.
        
        POST /api/productos/{id}/ajustar_stock/
        Body: {
            "cantidad": 10,
            "tipo": "ENTRADA" o "SALIDA",
            "costo_unitario": 1000,
            "observaciones": "Ajuste por inventario físico"
        }
        """
        producto = self.get_object()
        cantidad = request.data.get('cantidad')
        tipo_movimiento = request.data.get('tipo', 'AJUSTE')
        costo_unitario = request.data.get('costo_unitario', producto.precio_costo)
        observaciones = request.data.get('observaciones', '')
        
        if not cantidad:
            return Response(
                {'error': 'Debe proporcionar la cantidad'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cantidad = int(cantidad)
        except ValueError:
            return Response(
                {'error': 'La cantidad debe ser un número entero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear movimiento de inventario
        stock_anterior = producto.stock
        
        if tipo_movimiento in {'SALIDA', 'BAJA'}:
            cantidad = -abs(cantidad)  # Asegurar que sea negativo
        
        stock_nuevo = stock_anterior + cantidad
        
        if stock_nuevo < 0:
            return Response(
                {'error': 'El stock no puede ser negativo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        MovimientoInventario.objects.create(
            producto=producto,
            tipo=tipo_movimiento,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_nuevo=stock_nuevo,
            costo_unitario=costo_unitario,
            usuario=request.user,
            observaciones=observaciones
        )
        
        # Actualizar stock del producto
        producto.stock = stock_nuevo
        producto.save()
        
        serializer = ProductoDetailSerializer(producto)
        return Response(serializer.data)


class MovimientoInventarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar movimientos de inventario.
    Solo lectura (no se pueden editar movimientos).
    """
    queryset = MovimientoInventario.objects.select_related(
        'producto', 'usuario'
    ).all()
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['producto', 'tipo', 'usuario']
    search_fields = ['producto__codigo', 'producto__nombre', 'referencia']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['get'])
    def por_producto(self, request):
        """
        Retorna movimientos de un producto específico.
        
        GET /api/movimientos/por_producto/?producto_id=1
        """
        producto_id = request.query_params.get('producto_id', None)
        if not producto_id:
            return Response(
                {'error': 'Debe proporcionar el parámetro producto_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        movimientos = self.get_queryset().filter(producto_id=producto_id)
        serializer = self.get_serializer(movimientos, many=True)
        return Response(serializer.data)


class ProductoFavoritoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar productos favoritos del usuario.
    """
    serializer_class = ProductoFavoritoSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        return ProductoFavorito.objects.filter(
            usuario=self.request.user
        ).select_related('producto')

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
