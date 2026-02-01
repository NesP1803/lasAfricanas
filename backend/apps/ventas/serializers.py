from rest_framework import serializers
from .models import (
    Cliente,
    Venta,
    DetalleVenta,
    AuditoriaDescuento,
    SolicitudDescuento,
    VentaAnulada,
    Caja,
)
from apps.inventario.serializers import ProductoListSerializer
from apps.usuarios.models import Usuario


class ClienteSerializer(serializers.ModelSerializer):
    """Serializer para Clientes"""
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)
    total_compras = serializers.SerializerMethodField()
    
    class Meta:
        model = Cliente
        fields = [
            'id',
            'tipo_documento',
            'tipo_documento_display',
            'numero_documento',
            'nombre',
            'telefono',
            'email',
            'direccion',
            'ciudad',
            'is_active',
            'total_compras',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
        }
    
    def get_total_compras(self, obj):
        """Total de ventas del cliente"""
        return obj.ventas.filter(estado='CONFIRMADA').count()
    
    def validate_numero_documento(self, value):
        """Valida que el documento sea único"""
        instance = self.instance
        if instance:
            if Cliente.objects.exclude(pk=instance.pk).filter(numero_documento=value).exists():
                raise serializers.ValidationError("Ya existe un cliente con este documento")
        else:
            if Cliente.objects.filter(numero_documento=value).exists():
                raise serializers.ValidationError("Ya existe un cliente con este documento")
        return value


class DetalleVentaSerializer(serializers.ModelSerializer):
    """Serializer para detalles de venta"""
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    
    class Meta:
        model = DetalleVenta
        fields = [
            'id',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'cantidad',
            'precio_unitario',
            'descuento_unitario',
            'iva_porcentaje',
            'subtotal',
            'total'
        ]


class VentaListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados de ventas"""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_numero_documento = serializers.CharField(
        source='cliente.numero_documento',
        read_only=True
    )
    vendedor_nombre = serializers.CharField(source='vendedor.username', read_only=True)
    cajero_nombre = serializers.SerializerMethodField()
    caja_nombre = serializers.CharField(source='caja_destino.nombre', read_only=True, default=None)
    tipo_comprobante_display = serializers.CharField(source='get_tipo_comprobante_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    estado_pago_display = serializers.CharField(source='get_estado_pago_display', read_only=True)
    medio_pago_display = serializers.CharField(source='get_medio_pago_display', read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id',
            'numero_comprobante',
            'tipo_comprobante',
            'tipo_comprobante_display',
            'fecha',
            'cliente',
            'cliente_nombre',
            'cliente_numero_documento',
            'vendedor',
            'vendedor_nombre',
            'cajero',
            'cajero_nombre',
            'caja_destino',
            'caja_nombre',
            'total',
            'medio_pago',
            'medio_pago_display',
            'estado',
            'estado_display',
            'estado_pago',
            'estado_pago_display'
        ]

    def get_cajero_nombre(self, obj):
        if obj.cajero:
            return obj.cajero.get_full_name() or obj.cajero.username
        return None


class VentaDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de venta"""
    cliente_info = ClienteSerializer(source='cliente', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.get_full_name', read_only=True)
    cajero_nombre = serializers.SerializerMethodField()
    caja_nombre = serializers.CharField(source='caja_destino.nombre', read_only=True, default=None)
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    tipo_comprobante_display = serializers.CharField(source='get_tipo_comprobante_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    estado_pago_display = serializers.CharField(source='get_estado_pago_display', read_only=True)
    medio_pago_display = serializers.CharField(source='get_medio_pago_display', read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id',
            'tipo_comprobante',
            'tipo_comprobante_display',
            'numero_comprobante',
            'cliente',
            'cliente_info',
            'vendedor',
            'vendedor_nombre',
            'cajero',
            'cajero_nombre',
            'caja_destino',
            'caja_nombre',
            'fecha',
            'subtotal',
            'descuento_porcentaje',
            'descuento_valor',
            'iva',
            'total',
            'descuento_requiere_aprobacion',
            'descuento_aprobado_por',
            'estado_pago',
            'estado_pago_display',
            'fecha_cobro',
            'medio_pago',
            'medio_pago_display',
            'efectivo_recibido',
            'cambio',
            'estado',
            'estado_display',
            'observaciones',
            'remision_origen',
            'factura_electronica_uuid',
            'factura_electronica_cufe',
            'fecha_envio_dian',
            'detalles',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['numero_comprobante', 'created_at', 'updated_at']

    def get_cajero_nombre(self, obj):
        if obj.cajero:
            return obj.cajero.get_full_name() or obj.cajero.username
        return None


class VentaCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear ventas"""
    detalles = DetalleVentaSerializer(many=True)
    descuento_aprobado_por = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(),
        required=False,
        allow_null=True
    )
    caja_destino = serializers.PrimaryKeyRelatedField(
        queryset=Caja.objects.filter(is_active=True),
        required=False,
        allow_null=True
    )
    enviar_a_caja = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = Venta
        fields = [
            'tipo_comprobante',
            'cliente',
            'vendedor',
            'subtotal',
            'descuento_porcentaje',
            'descuento_valor',
            'iva',
            'total',
            'descuento_aprobado_por',
            'medio_pago',
            'efectivo_recibido',
            'cambio',
            'observaciones',
            'detalles',
            'caja_destino',
            'enviar_a_caja'
        ]

    def create(self, validated_data):
        """Crea la venta con sus detalles"""
        detalles_data = validated_data.pop('detalles')
        enviar_a_caja = validated_data.pop('enviar_a_caja', False)
        caja_destino = validated_data.get('caja_destino')

        # Si se envía a caja, establecer estado pendiente
        if enviar_a_caja and caja_destino:
            validated_data['estado_pago'] = 'PENDIENTE_CAJA'
            # No establecer medio_pago hasta que se procese en caja
            validated_data['medio_pago'] = 'EFECTIVO'  # Default temporal
            validated_data['efectivo_recibido'] = 0
            validated_data['cambio'] = 0

        venta = Venta.objects.create(**validated_data)

        for detalle_data in detalles_data:
            DetalleVenta.objects.create(venta=venta, **detalle_data)

        return venta


class VentaAnuladaSerializer(serializers.ModelSerializer):
    """Serializer para ventas anuladas"""
    venta_numero = serializers.CharField(source='venta.numero_comprobante', read_only=True)
    anulado_por_nombre = serializers.CharField(source='anulado_por.username', read_only=True)
    motivo_display = serializers.CharField(source='get_motivo_display', read_only=True)
    
    class Meta:
        model = VentaAnulada
        fields = [
            'id',
            'venta',
            'venta_numero',
            'motivo',
            'motivo_display',
            'descripcion',
            'anulado_por',
            'anulado_por_nombre',
            'devuelve_inventario',
            'created_at'
        ]
        read_only_fields = ['created_at']


class SolicitudDescuentoSerializer(serializers.ModelSerializer):
    """Serializer para solicitudes de descuento"""
    vendedor_nombre = serializers.CharField(source='vendedor.username', read_only=True)
    aprobador_nombre = serializers.CharField(source='aprobador.username', read_only=True)

    class Meta:
        model = SolicitudDescuento
        fields = [
            'id',
            'vendedor',
            'vendedor_nombre',
            'aprobador',
            'aprobador_nombre',
            'descuento_solicitado',
            'descuento_aprobado',
            'subtotal',
            'iva',
            'total_antes_descuento',
            'total_con_descuento',
            'estado',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'vendedor',
            'vendedor_nombre',
            'aprobador_nombre',
            'created_at',
            'updated_at',
        ]


class CajaSerializer(serializers.ModelSerializer):
    """Serializer para Cajas"""
    cajeros_count = serializers.SerializerMethodField()
    ventas_pendientes_count = serializers.SerializerMethodField()

    class Meta:
        model = Caja
        fields = [
            'id',
            'nombre',
            'descripcion',
            'ubicacion',
            'is_active',
            'cajeros_count',
            'ventas_pendientes_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_cajeros_count(self, obj):
        return obj.cajeros_asignados.count()

    def get_ventas_pendientes_count(self, obj):
        return obj.ventas_pendientes_count


class VentaPendienteCajaSerializer(serializers.ModelSerializer):
    """Serializer para ventas pendientes de cobro en caja"""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_numero_documento = serializers.CharField(
        source='cliente.numero_documento',
        read_only=True
    )
    vendedor_nombre = serializers.SerializerMethodField()
    tipo_comprobante_display = serializers.CharField(source='get_tipo_comprobante_display', read_only=True)
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    caja_nombre = serializers.CharField(source='caja_destino.nombre', read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id',
            'numero_comprobante',
            'tipo_comprobante',
            'tipo_comprobante_display',
            'fecha',
            'cliente',
            'cliente_nombre',
            'cliente_numero_documento',
            'vendedor',
            'vendedor_nombre',
            'subtotal',
            'descuento_porcentaje',
            'descuento_valor',
            'iva',
            'total',
            'caja_destino',
            'caja_nombre',
            'observaciones',
            'detalles',
        ]

    def get_vendedor_nombre(self, obj):
        return obj.vendedor.get_full_name() or obj.vendedor.username


class ProcesarPagoSerializer(serializers.Serializer):
    """Serializer para procesar pago en caja"""
    medio_pago = serializers.ChoiceField(choices=Venta.MEDIO_PAGO)
    efectivo_recibido = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=0
    )
    observaciones = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        medio_pago = data.get('medio_pago')
        efectivo_recibido = data.get('efectivo_recibido', 0)
        venta = self.context.get('venta')

        if medio_pago == 'EFECTIVO' and venta:
            if efectivo_recibido < venta.total:
                raise serializers.ValidationError({
                    'efectivo_recibido': f'El efectivo recibido debe ser mayor o igual al total ({venta.total})'
                })

        return data


class EnviarACajaSerializer(serializers.Serializer):
    """Serializer para enviar una venta a caja"""
    caja_destino = serializers.PrimaryKeyRelatedField(queryset=Caja.objects.filter(is_active=True))
