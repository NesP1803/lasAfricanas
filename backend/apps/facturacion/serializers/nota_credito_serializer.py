"""Serializers para recursos de notas crédito electrónicas."""

from __future__ import annotations

from rest_framework import serializers

from apps.facturacion.models import NotaCreditoDetalle, NotaCreditoElectronica


class CreditNoteLineInputSerializer(serializers.Serializer):
    detalle_venta_original_id = serializers.IntegerField()
    cantidad_a_acreditar = serializers.DecimalField(max_digits=12, decimal_places=2)
    afecta_inventario = serializers.BooleanField(default=False)
    motivo_linea = serializers.CharField(required=False, allow_blank=True, default='')


class NotaCreditoCreateSerializer(serializers.Serializer):
    factura_id = serializers.IntegerField(required=False)
    motivo = serializers.CharField()
    lines = CreditNoteLineInputSerializer(many=True, allow_empty=False)


class NotaCreditoPreviewSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True)
    lines = CreditNoteLineInputSerializer(many=True, allow_empty=False)


class NotaCreditoDetalleSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = NotaCreditoDetalle
        fields = [
            'id',
            'detalle_venta_original',
            'producto',
            'producto_nombre',
            'cantidad_original_facturada',
            'cantidad_ya_acreditada',
            'cantidad_a_acreditar',
            'precio_unitario',
            'descuento',
            'base_impuesto',
            'impuesto',
            'total_linea',
            'afecta_inventario',
            'motivo_linea',
        ]


class NotaCreditoListSerializer(serializers.ModelSerializer):
    numero = serializers.CharField(source='number', read_only=True)
    factura_asociada = serializers.CharField(source='factura.number', read_only=True)
    fecha = serializers.DateTimeField(source='created_at', read_only=True)
    estado = serializers.CharField(source='estado_local', read_only=True)
    estado_dian = serializers.CharField(source='estado_electronico', read_only=True)
    detalles = NotaCreditoDetalleSerializer(many=True, read_only=True)

    class Meta:
        model = NotaCreditoElectronica
        fields = [
            'id',
            'numero',
            'factura_asociada',
            'fecha',
            'motivo',
            'tipo_nota',
            'estado',
            'estado_dian',
            'estado_local',
            'estado_electronico',
            'reference_code',
            'cufe',
            'uuid',
            'xml_url',
            'pdf_url',
            'public_url',
            'correo_enviado',
            'correo_enviado_at',
            'codigo_error',
            'mensaje_error',
            'detalles',
        ]
        read_only_fields = fields
