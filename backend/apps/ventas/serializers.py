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

    @staticmethod
    def _to_decimal(value, default='0'):
        if value is None:
            return Decimal(default)
        return Decimal(str(value))

    @staticmethod
    def _q(value):
        return Decimal(value).quantize(Decimal('0.01'))

    def _calcular_detalle(self, detalle):
        cantidad = self._to_decimal(detalle.get('cantidad'))
        precio_unitario = self._to_decimal(detalle.get('precio_unitario'))
        descuento_unitario = self._to_decimal(detalle.get('descuento_unitario', 0))
        iva_porcentaje = self._to_decimal(detalle.get('iva_porcentaje', 0))

        subtotal_bruto = cantidad * precio_unitario
        descuento_linea = min(subtotal_bruto, cantidad * max(descuento_unitario, Decimal('0')))
        subtotal_neto = subtotal_bruto - descuento_linea
        iva_linea = (subtotal_neto * iva_porcentaje) / Decimal('100')
        total_linea = subtotal_neto + iva_linea

        detalle['subtotal'] = self._q(subtotal_neto)
        detalle['total'] = self._q(total_linea)

        return {
            'subtotal_neto': self._q(subtotal_neto),
            'iva_linea': self._q(iva_linea),
        }

    def _recalcular_totales(self, validated_data, detalles_data):
        subtotal = Decimal('0.00')
        iva = Decimal('0.00')

        for detalle in detalles_data:
            calculo = self._calcular_detalle(detalle)
            subtotal += calculo['subtotal_neto']
            iva += calculo['iva_linea']

        descuento_porcentaje = self._to_decimal(validated_data.get('descuento_porcentaje', 0))
        descuento_valor = self._to_decimal(validated_data.get('descuento_valor', 0))

        if descuento_porcentaje < 0 or descuento_valor < 0:
            raise serializers.ValidationError({'descuento_valor': 'El descuento no puede ser negativo.'})

        descuento_porcentaje_valor = (subtotal * descuento_porcentaje) / Decimal('100')
        descuento_total = descuento_valor if descuento_valor > 0 else descuento_porcentaje_valor
        descuento_total = min(descuento_total, subtotal)

        total = subtotal + iva - descuento_total

        validated_data['subtotal'] = self._q(subtotal)
        validated_data['iva'] = self._q(iva)
        validated_data['descuento_valor'] = self._q(descuento_total)
        validated_data['total'] = self._q(total)

        efectivo_recibido = validated_data.get('efectivo_recibido')
        if efectivo_recibido is not None:
            cambio = self._to_decimal(efectivo_recibido) - validated_data['total']
            validated_data['cambio'] = self._q(cambio if cambio > 0 else Decimal('0'))

    def create(self, validated_data):
        """Crea la venta con sus detalles y totales calculados en backend"""
        detalles_data = validated_data.pop('detalles', [])
        self._recalcular_totales(validated_data, detalles_data)

        venta = Venta.objects.create(**validated_data)

        for detalle_data in detalles_data:
            DetalleVenta.objects.create(venta=venta, **detalle_data)

        return venta

    def update(self, instance, validated_data):
        detalles_data = validated_data.pop('detalles', None)

        validated_data.setdefault('descuento_porcentaje', instance.descuento_porcentaje)
        validated_data.setdefault('descuento_valor', instance.descuento_valor)
        if 'efectivo_recibido' not in validated_data:
            validated_data['efectivo_recibido'] = instance.efectivo_recibido

        if detalles_data is None:
            detalles_data = [
                {
                    'producto': detalle.producto,
                    'cantidad': detalle.cantidad,
                    'precio_unitario': detalle.precio_unitario,
                    'descuento_unitario': detalle.descuento_unitario,
                    'iva_porcentaje': detalle.iva_porcentaje,
                    'subtotal': detalle.subtotal,
                    'total': detalle.total,
                    'afecto_inventario': detalle.afecto_inventario,
                }
                for detalle in instance.detalles.all()
            ]

        self._recalcular_totales(validated_data, detalles_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if self.initial_data.get('detalles') is not None:
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

        # Las cotizaciones NO pueden tener descuentos
        tipo_comprobante = attrs.get('tipo_comprobante') or getattr(self.instance, 'tipo_comprobante', None)
        if tipo_comprobante == 'COTIZACION':
            descuento_porcentaje = attrs.get('descuento_porcentaje', 0)
            descuento_valor = attrs.get('descuento_valor', 0)
            detalles = attrs.get('detalles', [])

            if descuento_porcentaje and float(descuento_porcentaje) > 0:
                raise serializers.ValidationError({
                    'descuento_porcentaje': 'Las cotizaciones no pueden tener descuentos. '
                    'Si el cliente desea un descuento, debe realizar la compra directamente como remisión o factura.'
                })
            if descuento_valor and float(descuento_valor) > 0:
                raise serializers.ValidationError({
                    'descuento_valor': 'Las cotizaciones no pueden tener descuentos. '
                    'Si el cliente desea un descuento, debe realizar la compra directamente como remisión o factura.'
                })
            # Validar descuentos en los detalles
            for idx, detalle in enumerate(detalles):
                descuento_unitario = detalle.get('descuento_unitario', 0)
                if descuento_unitario and float(descuento_unitario) > 0:
                    raise serializers.ValidationError({
                        'detalles': f'Las cotizaciones no pueden tener descuentos en los productos (línea {idx + 1}). '
                        'Si el cliente desea un descuento, debe realizar la compra directamente como remisión o factura.'
                    })

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
