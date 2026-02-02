from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Usuario, PerfilVendedor


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Configuración del admin para el modelo Usuario"""
    
    # Campos que se muestran en la lista
    list_display = [
        'username', 
        'email', 
        'get_full_name', 
        'tipo_usuario', 
        'es_cajero',
        'sede', 
        'is_active', 
        'is_staff'
    ]
    
    # Filtros en la barra lateral
    list_filter = [
        'tipo_usuario', 
        'es_cajero',
        'sede', 
        'is_active', 
        'is_staff', 
        'date_joined'
    ]
    
    # Campos para búsqueda
    search_fields = [
        'username', 
        'first_name', 
        'last_name', 
        'email'
    ]
    
    # Ordenamiento por defecto
    ordering = ['-date_joined']
    
    # Configuración de los fieldsets (cómo se agrupan los campos en el formulario)
    fieldsets = (
        ('Credenciales', {
            'fields': ('username', 'password')
        }),
        ('Información personal', {
            'fields': ('first_name', 'last_name', 'email', 'telefono')
        }),
        ('Información laboral', {
            'fields': ('tipo_usuario', 'es_cajero', 'sede')
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)  # Hace que esta sección esté colapsada por defecto
        }),
        ('Fechas importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    # Configuración para agregar nuevo usuario
    add_fieldsets = (
        ('Crear nuevo usuario', {
            'classes': ('wide',),
            'fields': (
                'username', 
                'password1', 
                'password2', 
                'first_name', 
                'last_name',
                'email',
                'tipo_usuario',
                'es_cajero',
                'sede',
                'is_staff',
                'is_active'
            ),
        }),
    )


@admin.register(PerfilVendedor)
class PerfilVendedorAdmin(admin.ModelAdmin):
    """Configuración del admin para el modelo PerfilVendedor"""
    
    list_display = [
        'usuario',
        'descuento_maximo',
        'puede_ver_costo',
        'puede_eliminar_ventas',
        'comision_porcentaje',
        'is_active'
    ]
    
    list_filter = [
        'puede_ver_costo',
        'puede_eliminar_ventas',
        'puede_modificar_precios',
        'is_active',
        'created_at'
    ]
    
    search_fields = [
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Usuario', {
            'fields': ('usuario',)
        }),
        ('Permisos de Descuentos', {
            'fields': ('descuento_maximo',)
        }),
        ('Permisos Operacionales', {
            'fields': (
                'puede_ver_costo',
                'puede_eliminar_ventas',
                'puede_modificar_precios'
            )
        }),
        ('Comisiones y Metas', {
            'fields': ('comision_porcentaje', 'meta_mensual')
        }),
        ('Estado', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimiza las consultas usando select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('usuario')
