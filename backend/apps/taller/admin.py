from django.contrib import admin
from django.utils.html import format_html
from .models import Mecanico, ServicioMoto, RepuestoAsignado, ConsumoRepuesto


@admin.register(Mecanico)
class MecanicoAdmin(admin.ModelAdmin):
    list_display = [
        'usuario',
        'especialidad',
        'total_cuentas_display',
        'servicios_activos_display',
        'comision_porcentaje',
        'is_active'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = [
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
        'especialidad'
    ]
    
    fieldsets = (
        ('Usuario', {
            'fields': ('usuario',)
        }),
        ('Información', {
            'fields': ('especialidad', 'comision_porcentaje')
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )
    
    def total_cuentas_display(self, obj):
        """Muestra el total en repuestos del mecánico"""
        total = obj.total_cuentas
        return format_html(
            '<span style="color: green; font-weight: bold;">${:,.2f}</span>',
            total
        )
    total_cuentas_display.short_description = 'Total Cuentas'
    
    def servicios_activos_display(self, obj):
        """Muestra cantidad de servicios activos"""
        count = obj.servicios_activos
        color = 'red' if count > 5 else 'green'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, count
        )
    servicios_activos_display.short_description = 'Servicios Activos'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('usuario')


class ConsumoRepuestoInline(admin.TabularInline):
    model = ConsumoRepuesto
    extra = 0
    fields = [
        'producto',
        'cantidad',
        'precio_unitario',
        'descuento',
        'subtotal',
        'descontado_de_mecanico'
    ]
    readonly_fields = ['subtotal', 'descontado_de_mecanico']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('producto')


@admin.register(ServicioMoto)
class ServicioMotoAdmin(admin.ModelAdmin):
    list_display = [
        'numero_servicio',
        'placa',
        'marca',
        'cliente',
        'mecanico',
        'estado_badge',
        'total_display',
        'fecha_ingreso'
    ]
    list_filter = [
        'estado',
        'mecanico',
        'fecha_ingreso',
        'marca'
    ]
    search_fields = [
        'numero_servicio',
        'placa',
        'cliente__nombre',
        'cliente__numero_documento',
        'marca',
        'modelo'
    ]
    ordering = ['-fecha_ingreso']
    inlines = [ConsumoRepuestoInline]
    
    fieldsets = (
        ('Servicio', {
            'fields': ('numero_servicio', 'estado')
        }),
        ('Moto', {
            'fields': (
                'placa',
                'marca',
                'modelo',
                'color',
                'kilometraje',
                'nivel_gasolina'
            )
        }),
        ('Cliente y Asignación', {
            'fields': (
                'cliente',
                'mecanico',
                'recibido_por'
            )
        }),
        ('Fechas', {
            'fields': (
                'fecha_ingreso',
                'fecha_estimada_entrega',
                'fecha_entrega_real'
            )
        }),
        ('Diagnóstico y Trabajo', {
            'fields': (
                'observaciones_ingreso',
                'diagnostico',
                'trabajo_realizado',
                'recomendaciones'
            )
        }),
        ('Costos', {
            'fields': (
                'costo_mano_obra',
                'costo_repuestos',
                'descuento',
                'total'
            )
        }),
        ('Facturación', {
            'fields': ('venta',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['numero_servicio', 'fecha_ingreso', 'costo_repuestos', 'total']
    
    def estado_badge(self, obj):
        """Muestra el estado con colores"""
        colores = {
            'INGRESADO': '#17a2b8',
            'EN_DIAGNOSTICO': '#ffc107',
            'COTIZADO': '#6c757d',
            'APROBADO': '#007bff',
            'EN_REPARACION': '#fd7e14',
            'TERMINADO': '#28a745',
            'ENTREGADO': '#20c997',
            'CANCELADO': '#dc3545',
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def total_display(self, obj):
        """Muestra el total formateado"""
        return format_html(
            '<span style="font-weight: bold;">${:,.2f}</span>',
            obj.total
        )
    total_display.short_description = 'Total'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('cliente', 'mecanico__usuario', 'recibido_por')


@admin.register(RepuestoAsignado)
class RepuestoAsignadoAdmin(admin.ModelAdmin):
    list_display = [
        'mecanico',
        'producto_info',
        'cantidad',
        'precio_unitario',
        'valor_total_display',
        'fecha_asignacion'
    ]
    list_filter = ['mecanico', 'fecha_asignacion', 'is_active']
    search_fields = [
        'mecanico__usuario__username',
        'producto__codigo',
        'producto__nombre'
    ]
    ordering = ['-fecha_asignacion']
    
    fieldsets = (
        ('Asignación', {
            'fields': ('mecanico', 'producto')
        }),
        ('Cantidad y Precio', {
            'fields': ('cantidad', 'precio_unitario')
        }),
        ('Estado', {
            'fields': ('is_active',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['fecha_asignacion']
    
    def producto_info(self, obj):
        """Muestra código y nombre del producto"""
        return f"{obj.producto.codigo} - {obj.producto.nombre}"
    producto_info.short_description = 'Producto'
    
    def valor_total_display(self, obj):
        """Muestra el valor total"""
        return format_html(
            '<span style="color: green; font-weight: bold;">${:,.2f}</span>',
            obj.valor_total
        )
    valor_total_display.short_description = 'Valor Total'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('mecanico__usuario', 'producto')


@admin.register(ConsumoRepuesto)
class ConsumoRepuestoAdmin(admin.ModelAdmin):
    list_display = [
        'servicio',
        'producto_info',
        'cantidad',
        'precio_unitario',
        'subtotal_display',
        'descontado_de_mecanico',
        'created_at'
    ]
    list_filter = [
        'descontado_de_mecanico',
        'stock_descontado',
        'created_at'
    ]
    search_fields = [
        'servicio__numero_servicio',
        'servicio__placa',
        'producto__codigo',
        'producto__nombre'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Servicio', {
            'fields': ('servicio',)
        }),
        ('Repuesto', {
            'fields': (
                'producto',
                'cantidad',
                'precio_unitario',
                'descuento',
                'subtotal'
            )
        }),
        ('Control', {
            'fields': (
                'registrado_por',
                'descontado_de_mecanico',
                'stock_descontado'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['subtotal', 'descontado_de_mecanico', 'stock_descontado']
    
    def producto_info(self, obj):
        """Muestra código y nombre del producto"""
        return f"{obj.producto.codigo} - {obj.producto.nombre}"
    producto_info.short_description = 'Producto'
    
    def subtotal_display(self, obj):
        """Muestra el subtotal formateado"""
        return format_html(
            '<span style="font-weight: bold;">${:,.2f}</span>',
            obj.subtotal
        )
    subtotal_display.short_description = 'Subtotal'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('servicio', 'producto', 'registrado_por')