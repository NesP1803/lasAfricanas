import re
from decimal import Decimal
from rest_framework import serializers

from apps.facturacion.services.factus_catalog_lookup import get_tribute_id
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
    def _resolve_factus_tribute_id(self, nombre: str, porcentaje: Decimal) -> int:
        if self._normalize_nombre(nombre).lower() == 'exento' or Decimal(porcentaje) == Decimal('0'):
            return int(get_tribute_id('ZZ', default=21))
        return int(get_tribute_id('IVA', default=18))

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

    def create(self, validated_data):
        nombre = validated_data.get('nombre', '')
        porcentaje = Decimal(validated_data.get('porcentaje', Decimal('0')))
        validated_data['factus_tribute_id'] = self._resolve_factus_tribute_id(nombre, porcentaje)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        nombre = validated_data.get('nombre', instance.nombre)
        porcentaje = Decimal(validated_data.get('porcentaje', instance.porcentaje))
        validated_data['factus_tribute_id'] = self._resolve_factus_tribute_id(nombre, porcentaje)
        return super().update(instance, validated_data)

    class Meta:
        model = Impuesto
        fields = '__all__'
        read_only_fields = ['factus_tribute_id']


class AuditoriaSerializer(serializers.ModelSerializer):
    ip_address = serializers.CharField(allow_null=True, required=False)

    class Meta:
        model = Auditoria
        fields = '__all__'
        read_only_fields = [
            'id', 'fecha_hora', 'usuario', 'usuario_nombre',
            'accion', 'modelo', 'objeto_id', 'notas', 'ip_address'
        ]
