"""Serializers para recursos de notas crédito electrónicas."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.facturacion.models import NotaCreditoElectronica


class NotaCreditoCreateSerializer(serializers.Serializer):
    """Contrato de creación para nota crédito vía API de recursos."""

    factura_id = serializers.IntegerField()
    motivo = serializers.CharField()
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class NotaCreditoListSerializer(serializers.ModelSerializer):
    """Contrato de listado retrocompatible para frontend de notas crédito."""

    numero = serializers.CharField(source='number', read_only=True)
    factura_asociada = serializers.CharField(source='factura.number', read_only=True)
    fecha = serializers.DateTimeField(source='created_at', read_only=True)
    estado = serializers.CharField(source='status', read_only=True)
    estado_dian = serializers.CharField(source='status', read_only=True)
    motivo = serializers.SerializerMethodField()

    class Meta:
        model = NotaCreditoElectronica
        fields = [
            'id',
            'numero',
            'factura_asociada',
            'fecha',
            'motivo',
            'estado',
            'estado_dian',
            'cufe',
            'uuid',
            'xml_url',
            'pdf_url',
        ]
        read_only_fields = fields

    def get_motivo(self, obj: NotaCreditoElectronica) -> str:
        payload: dict[str, Any] = obj.response_json or {}
        data = payload.get('data', payload) if isinstance(payload, dict) else {}
        note = data.get('credit_note', data) if isinstance(data, dict) else {}
        return str(
            note.get('credit_note_reason')
            or data.get('credit_note_reason')
            or payload.get('credit_note_reason')
            or ''
        ).strip()
