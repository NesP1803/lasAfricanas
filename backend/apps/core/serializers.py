import re
from decimal import Decimal
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
        extra_kwargs = {
            'correo': {'required': False, 'allow_blank': True},
        }


class ConfiguracionFacturacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionFacturacion
        fields = '__all__'


class ImpuestoSerializer(serializers.ModelSerializer):
    def _normalize_nombre(self, nombre: str) -> str:
        raw = (nombre or '').strip()
        if not raw:
            return raw
        lower = raw.lower()
        if lower in {'e', 'exento', 'excento'}:
            return 'Exento'
        match = re.search(r'(\d+(?:\.\d+)?)', raw)
        if match:
            porcentaje = match.group(1)
            porcentaje = porcentaje.rstrip('0').rstrip('.') or '0'
            if lower.startswith('iva') or raw.replace('%', '').strip().isdigit():
                return f'IVA {porcentaje}%'
        return raw

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['nombre'] = self._normalize_nombre(data.get('nombre'))
        return data

    def validate_nombre(self, value):
        return self._normalize_nombre(value)

    def _extract_porcentaje(self, nombre: str) -> Decimal:
        lower = (nombre or '').lower()
        if 'exento' in lower:
            return Decimal('0')
        match = re.search(r'(\d+(?:\.\d+)?)', nombre or '')
        if not match:
            return Decimal('0')
        return Decimal(match.group(1))

    def validate(self, attrs):
        nombre = attrs.get('nombre')
        if nombre is not None and 'porcentaje' not in attrs:
            attrs['porcentaje'] = self._extract_porcentaje(nombre)
        return attrs

    class Meta:
        model = Impuesto
        fields = '__all__'


class AuditoriaSerializer(serializers.ModelSerializer):
    ip_address = serializers.CharField(allow_null=True, required=False)

    class Meta:
        model = Auditoria
        fields = '__all__'
        read_only_fields = [
            'id', 'fecha_hora', 'usuario', 'usuario_nombre',
            'accion', 'modelo', 'objeto_id', 'notas', 'ip_address'
        ]
