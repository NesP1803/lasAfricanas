from rest_framework import serializers

from .models import (
    ConfiguracionEmpresa,
    ConfiguracionFacturacion,
    Impuesto,
    Auditoria,
)


class ConfiguracionEmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionEmpresa
        fields = '__all__'


class ConfiguracionFacturacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionFacturacion
        fields = '__all__'


class ImpuestoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Impuesto
        fields = '__all__'


class AuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auditoria
        fields = '__all__'
        read_only_fields = fields
