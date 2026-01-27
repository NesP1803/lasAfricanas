from django.contrib import admin

from .models import Template, TemplateVersion


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'output_type', 'is_active', 'updated_at')
    list_filter = ('document_type', 'output_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TemplateVersion)
class TemplateVersionAdmin(admin.ModelAdmin):
    list_display = ('template', 'version_number', 'created_by', 'created_at')
    list_filter = ('template__document_type', 'template__output_type')
    search_fields = ('template__name', 'comment')
    readonly_fields = ('created_at',)
