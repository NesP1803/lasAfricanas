from django.contrib import admin
from .models import Categoria, Proveedor, Producto, MovimientoInventario, ProductoFavorito


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'orden', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['nombre', 'descripcion']
    ordering = ['orden', 'nombre']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('nombre', 'descripcion', 'orden')
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'nit', 'telefono', 'ciudad', 'is_active']
    list_filter = ['is_active', 'ciudad', 'created_at']
    search_fields = ['nombre', 'nit', 'telefono', 'email', 'contacto']
    ordering = ['nombre']
    
    fieldsets = (
        ('Información básica', {
            'fields': ('nombre', 'nit')
        }),
        ('Contacto', {
            'fields': ('contacto', 'telefono', 'email')
        }),
        ('Ubicación', {
            'fields': ('direccion', 'ciudad')
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = [
        'codigo',
        'nombre',
        'categoria',
        'proveedor',
        'precio_venta',
        'stock',
        'stock_bajo_badge',
        'is_active'
    ]
    list_filter = [
        'categoria',
        'proveedor',
        'is_active',
        'es_servicio',
        'aplica_descuento'
    ]
    search_fields = ['codigo', 'nombre', 'descripcion']
    ordering = ['nombre']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo', 'nombre', 'descripcion')
        }),
        ('Clasificación', {
            'fields': ('categoria', 'proveedor')
        }),
        ('Precios', {
            'fields': (
                'precio_costo',
                'precio_venta',
                'precio_venta_minimo',
                'iva_porcentaje'
            )
        }),
        ('Inventario', {
            'fields': ('stock', 'stock_minimo', 'unidad_medida')
        }),
        ('Configuración', {
            'fields': ('aplica_descuento', 'es_servicio')
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def stock_bajo_badge(self, obj):
        """Muestra badge si el stock está bajo"""
        if obj.stock_bajo:
            return '🔴 Stock Bajo'
        return '✅ OK'
    stock_bajo_badge.short_description = 'Estado Stock'
    
    def get_queryset(self, request):
        """Optimiza consultas"""
        qs = super().get_queryset(request)
        return qs.select_related('categoria', 'proveedor')


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'producto',
        'tipo',
        'cantidad',
        'stock_anterior',
        'stock_nuevo',
        'usuario',
        'referencia'
    ]
    list_filter = ['tipo', 'created_at', 'usuario']
    search_fields = [
        'producto__codigo',
        'producto__nombre',
        'referencia',
        'observaciones'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Movimiento', {
            'fields': (
                'producto',
                'tipo',
                'cantidad',
                'stock_anterior',
                'stock_nuevo'
            )
        }),
        ('Costo', {
            'fields': ('costo_unitario',)
        }),
        ('Referencia', {
            'fields': ('referencia', 'observaciones', 'usuario')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('producto', 'usuario')


@admin.register(ProductoFavorito)
class ProductoFavoritoAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'producto', 'alias', 'orden', 'created_at']
    list_filter = ['usuario', 'created_at']
    search_fields = ['producto__codigo', 'producto__nombre', 'alias', 'usuario__username']
    ordering = ['usuario', 'orden', '-created_at']
