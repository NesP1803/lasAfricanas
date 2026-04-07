"""Serializers de facturación electrónica."""

from rest_framework import serializers

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.electronic_state_machine import resolve_actions


class FacturaElectronicaSerializer(serializers.ModelSerializer):
    """Serializer de lectura para trazabilidad completa del documento electrónico."""
    status = serializers.CharField(source='estado_electronico', read_only=True)

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
            'public_url',
            'qr_data',
            'qr_image_url',
            'qr_image_data',
            'xml_local_path',
            'pdf_local_path',
            'email_subject',
            'email_zip_local_path',
            'email_sent_at',
            'email_last_error',
            'send_email_enabled',
            'last_assets_sync_at',
            'pdf_uploaded_to_factus',
            'pdf_uploaded_at',
            'correo_enviado',
            'correo_enviado_at',
            'ultimo_error_correo',
            'ultimo_error_pdf',
            'qr',
            'status',
            'estado_electronico',
            'estado_factus_raw',
            'codigo_error',
            'mensaje_error',
            'observaciones_json',
            'response_json',
            'retry_count',
            'last_retry_at',
            'next_retry_at',
            'ultima_sincronizacion_at',
            'emitida_en_factus',
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

    status = serializers.CharField(source='estado_electronico', read_only=True)
    estado = serializers.CharField(source='estado_electronico', read_only=True)
    estado_dian = serializers.CharField(source='estado_electronico', read_only=True)
    acciones_sugeridas = serializers.SerializerMethodField()
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
            'estado_electronico',
            'estado_factus_raw',
            'estado',
            'estado_dian',
            'codigo_error',
            'mensaje_error',
            'observaciones_json',
            'retry_count',
            'last_retry_at',
            'next_retry_at',
            'ultima_sincronizacion_at',
            'emitida_en_factus',
            'pdf_url',
            'xml_url',
            'public_url',
            'qr_data',
            'qr_image_url',
            'qr_image_data',
            'xml_local_path',
            'pdf_local_path',
            'email_subject',
            'email_zip_local_path',
            'email_sent_at',
            'email_last_error',
            'send_email_enabled',
            'last_assets_sync_at',
            'pdf_uploaded_to_factus',
            'pdf_uploaded_at',
            'correo_enviado',
            'correo_enviado_at',
            'ultimo_error_correo',
            'ultimo_error_pdf',
            'qr',
            'updated_at',
            'acciones_sugeridas',
        ]
        read_only_fields = fields

    def get_acciones_sugeridas(self, obj: FacturaElectronica):
        return resolve_actions(obj.estado_electronico)


from .configuracion_dian_serializer import ConfiguracionDIANSerializer
from .documento_soporte_serializer import DocumentoSoporteCreateSerializer, DocumentoSoporteListSerializer
from .nota_credito_serializer import (
    NotaCreditoCreateSerializer,
    NotaCreditoListSerializer,
    NotaCreditoPreviewSerializer,
)
from .numbering_ranges_serializer import (
    CreateRangoFactusSerializer,
    LocalRangoNumeracionSerializer,
    RangoNumeracionDIANSerializer,
    RemisionNumeracionHistorialSerializer,
    RemisionNumeracionSerializer,
    SelectActiveRangeSerializer,
    UpdateConsecutivoSerializer,
)

__all__ = [
    'FacturaElectronicaSerializer',
    'FacturarVentaResponseSerializer',
    'FacturaEstadoSerializer',
    'ConfiguracionDIANSerializer',
    'NotaCreditoCreateSerializer',
    'NotaCreditoListSerializer',
    'NotaCreditoPreviewSerializer',
    'DocumentoSoporteCreateSerializer',
    'DocumentoSoporteListSerializer',
    'RangoNumeracionDIANSerializer',
    'CreateRangoFactusSerializer',
    'LocalRangoNumeracionSerializer',
    'UpdateConsecutivoSerializer',
    'SelectActiveRangeSerializer',
    'RemisionNumeracionSerializer',
    'RemisionNumeracionHistorialSerializer',
]
