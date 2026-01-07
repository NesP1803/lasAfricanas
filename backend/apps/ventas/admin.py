from django.contrib import admin
from .models import Cliente, Venta, DetalleVenta, AuditoriaDescuento, VentaAnulada


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = [
        'numero_documento',
        'nombre',
        'telefono',
        'ciudad',
        'is_active'
    ]
    list_filter = ['tipo_documento', 'ciudad', 'is_active', 'created_at']
    search_fields = ['numero_documento', 'nombre', 'telefono', 'email']
    ordering = ['nombre']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('tipo_documento', 'numero_documento', 'nombre')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email', 'direccion', 'ciudad')
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0
    fields = [
        'producto',
        'cantidad',
        'precio_unitario',
        'iva_porcentaje',
        'subtotal',
        'total'
    ]
    readonly_fields = ['subtotal', 'total']


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = [
        'numero_comprobante',
        'tipo_comprobante',
        'fecha',
        'cliente',
        'vendedor',
        'total',
        'estado',
        'badge_factura_electronica'
    ]
    list_filter = [
        'tipo_comprobante',
        'estado',
        'medio_pago',
        'fecha',
        'vendedor'
    ]
    search_fields = [
        'numero_comprobante',
        'cliente__nombre',
        'cliente__numero_documento',
        'factura_electronica_uuid'
    ]
    ordering = ['-fecha']
    inlines = [DetalleVentaInline]
    
    fieldsets = (
        ('Comprobante', {
            'fields': (
                'tipo_comprobante',
                'numero_comprobante',
                'estado'
            )
        }),
        ('Partes', {
            'fields': ('cliente', 'vendedor')
        }),
        ('Totales', {
            'fields': (
                'subtotal',
                'descuento_porcentaje',
                'descuento_valor',
                'iva',
                'total'
            )
        }),
        ('Descuentos', {
            'fields': (
                'descuento_requiere_aprobacion',
                'descuento_aprobado_por'
            ),
            'classes': ('collapse',)
        }),
        ('Pago', {
            'fields': (
                'medio_pago',
                'efectivo_recibido',
                'cambio'
            )
        }),
        ('Facturación Electrónica', {
            'fields': (
                'remision_origen',
                'factura_electronica_uuid',
                'factura_electronica_cufe',
                'fecha_envio_dian'
            ),
            'classes': ('collapse',)
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['numero_comprobante', 'fecha', 'created_at', 'updated_at']
    
    def badge_factura_electronica(self, obj):
        if obj.tipo_comprobante == 'FACTURA' and obj.factura_electronica_uuid:
            return '✅ Enviada DIAN'
        elif obj.tipo_comprobante == 'FACTURA':
            return '⏳ Pendiente DIAN'
        return '-'
    badge_factura_electronica.short_description = 'DIAN'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('cliente', 'vendedor', 'remision_origen')


@admin.register(AuditoriaDescuento)
class AuditoriaDescuentoAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'venta',
        'vendedor',
        'descuento_solicitado',
        'descuento_permitido',
        'requirio_aprobacion',
        'aprobado_por'
    ]
    list_filter = ['requirio_aprobacion', 'created_at', 'vendedor']
    search_fields = [
        'venta__numero_comprobante',
        'vendedor__username',
        'aprobado_por__username'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('venta', 'vendedor', 'aprobado_por')


@admin.register(VentaAnulada)
class VentaAnuladaAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'venta',
        'motivo',
        'anulado_por',
        'devuelve_inventario'
    ]
    list_filter = ['motivo', 'devuelve_inventario', 'created_at']
    search_fields = [
        'venta__numero_comprobante',
        'descripcion',
        'anulado_por__username'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('venta', 'anulado_por')