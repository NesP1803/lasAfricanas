from decimal import Decimal
from rest_framework import serializers
from .models import (
    Cliente,
    Venta,
    DetalleVenta,
    AuditoriaDescuento,
    SolicitudDescuento,
    VentaAnulada,
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
        return obj.ventas.filter(estado='FACTURADA').count()
    
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
    unidad_medida = serializers.CharField(source='producto.unidad_medida', read_only=True)
    
    class Meta:
        model = DetalleVenta
        fields = [
            'id',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'unidad_medida',
            'cantidad',
            'precio_unitario',
            'descuento_unitario',
            'iva_porcentaje',
            'subtotal',
            'total'
        ]

    def validate(self, attrs):
        producto = attrs.get('producto')
        cantidad = attrs.get('cantidad')
        if producto and cantidad:
            try:
                decimal_cantidad = Decimal(str(cantidad))
            except Exception:
                raise serializers.ValidationError({'cantidad': 'Cantidad inválida.'})
            if producto.unidad_medida == 'N/A' and decimal_cantidad != decimal_cantidad.quantize(Decimal('1')):
                raise serializers.ValidationError(
                    {'cantidad': 'Para unidad N/A solo se permiten enteros.'}
                )
        return attrs


class VentaListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados de ventas"""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    cliente_numero_documento = serializers.CharField(
        source='cliente.numero_documento',
        read_only=True
    )
    vendedor_nombre = serializers.CharField(source='vendedor.username', read_only=True)
    tipo_comprobante_display = serializers.CharField(source='get_tipo_comprobante_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    medio_pago_display = serializers.CharField(source='get_medio_pago_display', read_only=True)
    
    class Meta:
        model = Venta
        fields = [
            'id',
            'numero_comprobante',
            'tipo_comprobante',
            'tipo_comprobante_display',
            'fecha',
            'facturada_at',
            'enviada_a_caja_at',
            'cliente',
            'cliente_nombre',
            'cliente_numero_documento',
            'vendedor',
            'vendedor_nombre',
            'total',
            'medio_pago',
            'medio_pago_display',
            'estado',
            'estado_display'
        ]


class VentaDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de venta"""
    cliente_info = ClienteSerializer(source='cliente', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.get_full_name', read_only=True)
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    tipo_comprobante_display = serializers.CharField(source='get_tipo_comprobante_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
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
            'fecha',
            'subtotal',
            'descuento_porcentaje',
            'descuento_valor',
            'iva',
            'total',
            'descuento_requiere_aprobacion',
            'descuento_aprobado_por',
            'medio_pago',
            'medio_pago_display',
            'efectivo_recibido',
            'cambio',
            'estado',
            'estado_display',
            'creada_por',
            'enviada_a_caja_por',
            'enviada_a_caja_at',
            'facturada_por',
            'facturada_at',
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


class VentaCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear ventas"""
    detalles = DetalleVentaSerializer(many=True, required=False)
    descuento_aprobado_por = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.all(),
        required=False,
        allow_null=True
    )
    
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
            'detalles'
        ]
    
    def create(self, validated_data):
        """Crea la venta con sus detalles"""
        detalles_data = validated_data.pop('detalles', [])
        venta = Venta.objects.create(**validated_data)
        
        for detalle_data in detalles_data:
            DetalleVenta.objects.create(venta=venta, **detalle_data)
        
        return venta

    def update(self, instance, validated_data):
        detalles_data = validated_data.pop('detalles', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if detalles_data is not None:
            instance.detalles.all().delete()
            for detalle_data in detalles_data:
                DetalleVenta.objects.create(venta=instance, **detalle_data)
        return instance

    def validate(self, attrs):
        if self.instance is None:
            detalles = attrs.get('detalles')
            if not detalles:
                raise serializers.ValidationError(
                    {'detalles': 'Debe incluir al menos un detalle.'}
                )
        return attrs


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
