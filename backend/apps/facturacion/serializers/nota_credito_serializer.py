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
    lines = CreditNoteLineInputSerializer(many=True, allow_empty=False, required=False)
    items = CreditNoteLineInputSerializer(many=True, allow_empty=False, required=False, write_only=True)

    def validate(self, attrs):
        lines = attrs.get('lines') or attrs.get('items')
        if not lines:
            raise serializers.ValidationError({'lines': 'Debe enviar al menos una línea en "lines".'})
        attrs['lines'] = lines
        return attrs


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
    numero = serializers.SerializerMethodField()
    factura_asociada = serializers.CharField(source='factura.number', read_only=True)
    fecha = serializers.DateTimeField(source='created_at', read_only=True)
    estado = serializers.CharField(source='estado_local', read_only=True)
    estado_dian = serializers.CharField(source='estado_electronico', read_only=True)
    can_sync = serializers.SerializerMethodField()
    estado_ui_mensaje = serializers.SerializerMethodField()
    request_numbering_range_id = serializers.SerializerMethodField()
    range_prefix = serializers.SerializerMethodField()
    range_resolution = serializers.SerializerMethodField()
    detalles = NotaCreditoDetalleSerializer(many=True, read_only=True)

    def get_can_sync(self, obj: NotaCreditoElectronica) -> bool:
        return obj.estado_local in {'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'}

    def get_estado_ui_mensaje(self, obj: NotaCreditoElectronica) -> str:
        if obj.estado_local in {'CONFLICTO_FACTUS', 'PENDIENTE_DIAN', 'PENDIENTE_ENVIO'}:
            return 'Documento en proceso DIAN/Factus. El sistema sincroniza automáticamente.'
        if obj.estado_local == 'ACEPTADA':
            return 'Documento aceptado electrónicamente.'
        if obj.estado_local == 'RECHAZADA':
            return 'Documento rechazado electrónicamente.'
        return ''

    def get_numero(self, obj: NotaCreditoElectronica) -> str:
        return str(obj.number or '').strip()

    def get_request_numbering_range_id(self, obj: NotaCreditoElectronica) -> int | None:
        request_json = obj.request_json if isinstance(obj.request_json, dict) else {}
        value = request_json.get('numbering_range_id')
        try:
            return int(value) if value not in (None, '') else None
        except (TypeError, ValueError):
            return None

    def get_range_prefix(self, obj: NotaCreditoElectronica) -> str:
        sync_meta = obj.sync_metadata if isinstance(obj.sync_metadata, dict) else {}
        request_json = obj.request_json if isinstance(obj.request_json, dict) else {}
        range_trace = request_json.get('range_trace') if isinstance(request_json.get('range_trace'), dict) else {}
        return str(sync_meta.get('range_prefix') or range_trace.get('range_prefix') or '').strip()

    def get_range_resolution(self, obj: NotaCreditoElectronica) -> str:
        sync_meta = obj.sync_metadata if isinstance(obj.sync_metadata, dict) else {}
        request_json = obj.request_json if isinstance(obj.request_json, dict) else {}
        range_trace = request_json.get('range_trace') if isinstance(request_json.get('range_trace'), dict) else {}
        return str(sync_meta.get('range_resolution') or range_trace.get('range_resolution') or '').strip()

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
            'email_status',
            'codigo_error',
            'mensaje_error',
            'status_raw_factus',
            'remote_status_raw',
            'synchronized_at',
            'last_sync_at',
            'last_remote_error',
            'remote_identifier',
            'sync_metadata',
            'request_numbering_range_id',
            'range_prefix',
            'range_resolution',
            'can_sync',
            'estado_ui_mensaje',
            'detalles',
        ]
        read_only_fields = fields
