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
from apps.usuarios.models import Usuario
from apps.ventas.services.calculo_venta import calcular_detalle_venta, recalcular_totales_venta
from apps.facturacion.services.public_invoice_url import has_documental_inconsistency, resolve_public_invoice_url


def _build_factura_electronica_data(venta):
    factura = getattr(venta, 'factura_electronica_factus', None)
    if not factura:
        return None
    response_json = factura.response_json if isinstance(factura.response_json, dict) else {}
    final_fields = response_json.get('final_fields', {}) if isinstance(response_json.get('final_fields', {}), dict) else {}
    response_data = response_json.get('data', {}) if isinstance(response_json.get('data', {}), dict) else {}
    response_bill = response_data.get('bill', {}) if isinstance(response_data.get('bill', {}), dict) else {}
    bill_errors = response_json.get('bill_errors', [])
    public_url = resolve_public_invoice_url(factura)
    documento_inconsistente = has_documental_inconsistency(factura)
    return {
        'id': factura.id,
        'venta_id': factura.venta_id,
        'numero': factura.number,
        'reference_code': factura.reference_code,
        'cufe': factura.cufe,
        'uuid': factura.uuid,
        'status': factura.estado_electronico or factura.status,
        'estado_dian': factura.estado_electronico or factura.status,
        'estado': factura.estado_electronico or factura.status,
        'codigo_error': factura.codigo_error,
        'observaciones': factura.mensaje_error or '',
        'bill_errors': bill_errors if isinstance(bill_errors, list) else [],
        'public_url': public_url,
        'factus_public_url': public_url,
        'documento_inconsistente': documento_inconsistente,
        'mensaje_inconsistencia_documental': factura.mensaje_error if documento_inconsistente else '',
        'qr_factus': final_fields.get('qr', ''),
        'qr_image': final_fields.get('qr_image', '') or factura.qr_image_url or factura.qr_image_data or '',
        'xml_url': factura.xml_url,
        'pdf_url': factura.pdf_url,
    }


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
        return obj.ventas.filter(estado='COBRADA').count()
    
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
    producto_stock = serializers.DecimalField(source='producto.stock', max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = DetalleVenta
        fields = [
            'id',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'unidad_medida',
            'producto_stock',
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
    estado_venta = serializers.CharField(source='estado', read_only=True)
    estado_electronico = serializers.SerializerMethodField()
    factura_electronica = serializers.SerializerMethodField()
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
            'estado_display',
            'estado_venta',
            'estado_electronico',
            'factura_electronica',
        ]

    def get_estado_electronico(self, obj):
        factura = getattr(obj, 'factura_electronica_factus', None)
        if not factura:
            return None
        return factura.estado_electronico or factura.status

    def get_factura_electronica(self, obj):
        return _build_factura_electronica_data(obj)


class VentaDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de venta"""
    cliente_info = ClienteSerializer(source='cliente', read_only=True)
    vendedor_nombre = serializers.CharField(source='vendedor.get_full_name', read_only=True)
    detalles = DetalleVentaSerializer(many=True, read_only=True)
    tipo_comprobante_display = serializers.CharField(source='get_tipo_comprobante_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    estado_venta = serializers.CharField(source='estado', read_only=True)
    estado_electronico = serializers.SerializerMethodField()
    factura_electronica = serializers.SerializerMethodField()
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
            'estado_venta',
            'estado_electronico',
            'factura_electronica',
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

    def get_estado_electronico(self, obj):
        factura = getattr(obj, 'factura_electronica_factus', None)
        if not factura:
            return None
        return factura.estado_electronico or factura.status

    def get_factura_electronica(self, obj):
        return _build_factura_electronica_data(obj)


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
            'inventario_ya_afectado',
            'detalles'
        ]
        extra_kwargs = {
            'vendedor': {'required': False},
        }


    def _calcular_detalle(self, detalle):
        return calcular_detalle_venta(detalle)

    def _strip_manual_totals(self, validated_data):
        for field in ('subtotal', 'iva', 'total', 'cambio'):
            validated_data.pop(field, None)

    def _recalcular_totales(self, validated_data, detalles_data):
        self._strip_manual_totals(validated_data)
        try:
            totales = recalcular_totales_venta(
                detalles_data=detalles_data,
                descuento_porcentaje=validated_data.get('descuento_porcentaje', 0),
                descuento_valor=validated_data.get('descuento_valor', 0),
                efectivo_recibido=validated_data.get('efectivo_recibido'),
            )
        except ValueError as error:
            raise serializers.ValidationError({'descuento_valor': str(error)})

        validated_data.update(totales)

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
