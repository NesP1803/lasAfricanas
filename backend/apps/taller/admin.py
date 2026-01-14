from django.contrib import admin
from .models import Mecanico, Moto, OrdenTaller, OrdenRepuesto


@admin.register(Mecanico)
class MecanicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'email', 'ciudad', 'is_active')
    search_fields = ('nombre', 'telefono', 'email')
    list_filter = ('is_active', 'ciudad')


@admin.register(Moto)
class MotoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'marca', 'modelo', 'mecanico', 'cliente', 'proveedor', 'is_active')
    search_fields = ('placa', 'marca', 'modelo')
    list_filter = ('is_active', 'marca')


class OrdenRepuestoInline(admin.TabularInline):
    model = OrdenRepuesto
    extra = 0


@admin.register(OrdenTaller)
class OrdenTallerAdmin(admin.ModelAdmin):
    list_display = ('id', 'moto', 'mecanico', 'estado', 'venta', 'created_at')
    list_filter = ('estado', 'mecanico')
    search_fields = ('moto__placa', 'mecanico__nombre')
    inlines = [OrdenRepuestoInline]
