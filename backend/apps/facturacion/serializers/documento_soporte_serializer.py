"""Serializers para recursos de documentos soporte electrónicos."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from rest_framework import serializers

from apps.facturacion.models import DocumentoSoporteElectronico


class DocumentoSoporteCreateSerializer(serializers.Serializer):
    """Contrato de creación para documento soporte vía API de recursos."""

    proveedor_nombre = serializers.CharField()
    proveedor_documento = serializers.CharField()
    proveedor_tipo_documento = serializers.CharField(required=False, allow_blank=True, default='CC')
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class DocumentoSoporteListSerializer(serializers.ModelSerializer):
    """Contrato de listado retrocompatible para frontend de documentos soporte."""

    numero = serializers.CharField(source='number', read_only=True)
    fecha = serializers.DateTimeField(source='created_at', read_only=True)
    estado = serializers.CharField(source='status', read_only=True)
    estado_dian = serializers.CharField(source='status', read_only=True)
    total = serializers.SerializerMethodField()
    can_sync = serializers.SerializerMethodField()
    reference_code = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoSoporteElectronico
        fields = [
            'id',
            'numero',
            'proveedor_nombre',
            'proveedor_documento',
            'proveedor_tipo_documento',
            'fecha',
            'total',
            'estado',
            'estado_dian',
            'cufe',
            'uuid',
            'xml_url',
            'pdf_url',
            'reference_code',
            'can_sync',
        ]
        read_only_fields = fields

    def get_total(self, obj: DocumentoSoporteElectronico) -> float:
        payload: dict[str, Any] = obj.response_json or {}
        data = payload.get('data', payload) if isinstance(payload, dict) else {}
        support_document = data.get('support_document', data) if isinstance(data, dict) else {}

        candidates = [
            support_document.get('total'),
            support_document.get('totals', {}).get('total') if isinstance(support_document.get('totals'), dict) else None,
            data.get('total') if isinstance(data, dict) else None,
            data.get('totals', {}).get('total') if isinstance(data, dict) and isinstance(data.get('totals'), dict) else None,
        ]
        for value in candidates:
            if value is None or value == '':
                continue
            try:
                return float(Decimal(str(value)))
            except (InvalidOperation, TypeError, ValueError):
                continue
        return 0.0

    def get_can_sync(self, obj: DocumentoSoporteElectronico) -> bool:
        return str(obj.status or '').strip().upper() in {'EN_PROCESO', 'PENDIENTE_DIAN', 'PENDIENTE', 'CONFLICTO_FACTUS'}

    def get_reference_code(self, obj: DocumentoSoporteElectronico) -> str:
        payload: dict[str, Any] = obj.response_json or {}
        data = payload.get('data', payload) if isinstance(payload, dict) else {}
        support_document = data.get('support_document', data) if isinstance(data, dict) else {}
        return str(
            support_document.get('reference_code')
            or data.get('reference_code')
            or payload.get('reference_code')
            or obj.number
            or ''
        ).strip()
