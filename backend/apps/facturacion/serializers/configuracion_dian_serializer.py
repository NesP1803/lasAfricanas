"""Serializers para configuración DIAN."""

from rest_framework import serializers

from apps.facturacion.models import ConfiguracionDIAN


class ConfiguracionDIANSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionDIAN
        fields = [
            'id',
            'nit_empresa',
            'software_id',
            'software_pin',
            'prefijo_facturacion',
            'rango_facturacion',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
