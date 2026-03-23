"""Serializers de facturación electrónica."""

from rest_framework import serializers

from apps.facturacion.models import FacturaElectronica


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
            'reference_code',
            'xml_url',
            'pdf_url',
            'qr',
            'status',
            'codigo_error',
            'mensaje_error',
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


class FacturaEstadoSerializer(serializers.ModelSerializer):
    """Serializer de respuesta para consulta de estado DIAN sincronizado."""

    estado = serializers.CharField(source='status', read_only=True)
    estado_dian = serializers.CharField(source='status', read_only=True)
    numero = serializers.CharField(source='number', read_only=True)

    class Meta:
        model = FacturaElectronica
        fields = [
            'number',
            'numero',
            'reference_code',
            'cufe',
            'uuid',
            'status',
            'estado',
            'estado_dian',
            'codigo_error',
            'mensaje_error',
            'pdf_url',
            'xml_url',
            'qr',
            'updated_at',
        ]
        read_only_fields = fields


from .configuracion_dian_serializer import ConfiguracionDIANSerializer
from .documento_soporte_serializer import DocumentoSoporteCreateSerializer, DocumentoSoporteListSerializer
from .nota_credito_serializer import NotaCreditoCreateSerializer, NotaCreditoListSerializer

__all__ = [
    'FacturaElectronicaSerializer',
    'FacturarVentaResponseSerializer',
    'FacturaEstadoSerializer',
    'ConfiguracionDIANSerializer',
    'NotaCreditoCreateSerializer',
    'NotaCreditoListSerializer',
    'DocumentoSoporteCreateSerializer',
    'DocumentoSoporteListSerializer',
]
