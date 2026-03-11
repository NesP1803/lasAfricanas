"""Serializers de facturación electrónica."""

from rest_framework import serializers

from .models import FacturaElectronica


class FacturaElectronicaSerializer(serializers.ModelSerializer):
    """Serializer de lectura para trazabilidad completa del documento electrónico."""

    class Meta:
        model = FacturaElectronica
        fields = [
            'id',
            'venta',
            'cufe',
            'uuid',
            'number',
            'xml_url',
            'pdf_url',
            'qr',
            'status',
            'response_json',
            'created_at',
        ]
        read_only_fields = fields


class FacturarVentaResponseSerializer(serializers.Serializer):
    """Contrato de respuesta para el endpoint POST /ventas/{id}/facturar/."""

    message = serializers.CharField()
    cufe = serializers.CharField()
    numero = serializers.CharField()
    pdf_url = serializers.URLField()
    xml_url = serializers.URLField()
