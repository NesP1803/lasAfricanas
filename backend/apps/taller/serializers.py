from decimal import Decimal
from rest_framework import serializers
from apps.inventario.models import Producto
from apps.ventas.models import Cliente
from .models import Mecanico, Moto, OrdenTaller, OrdenRepuesto


class MecanicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mecanico
        fields = [
            'id',
            'nombre',
            'telefono',
            'email',
            'direccion',
            'ciudad',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
        }


class MotoSerializer(serializers.ModelSerializer):
    mecanico_nombre = serializers.CharField(source='mecanico.nombre', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)

    class Meta:
        model = Moto
        fields = [
            'id',
            'placa',
            'marca',
            'modelo',
            'color',
            'anio',
            'cliente',
            'cliente_nombre',
            'mecanico',
            'mecanico_nombre',
            'proveedor',
            'proveedor_nombre',
            'observaciones',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_placa(self, value):
        instance = self.instance
        if instance:
            if Moto.objects.exclude(pk=instance.pk).filter(placa=value).exists():
                raise serializers.ValidationError('Ya existe una moto con esta placa')
        else:
            if Moto.objects.filter(placa=value).exists():
                raise serializers.ValidationError('Ya existe una moto con esta placa')
        return value


class OrdenRepuestoSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    iva_porcentaje = serializers.DecimalField(source='producto.iva_porcentaje', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = OrdenRepuesto
        fields = [
            'id',
            'orden',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'cantidad',
            'precio_unitario',
            'subtotal',
            'iva_porcentaje',
        ]
        read_only_fields = ['subtotal']


class OrdenTallerSerializer(serializers.ModelSerializer):
    repuestos = OrdenRepuestoSerializer(many=True, required=False)
    mecanico_nombre = serializers.CharField(source='mecanico.nombre', read_only=True)
    moto_placa = serializers.CharField(source='moto.placa', read_only=True)
    moto_marca = serializers.CharField(source='moto.marca', read_only=True)
    moto_modelo = serializers.CharField(source='moto.modelo', read_only=True)
    total = serializers.SerializerMethodField()
    venta_numero = serializers.CharField(source='venta.numero_comprobante', read_only=True)

    class Meta:
        model = OrdenTaller
        fields = [
            'id',
            'moto',
            'moto_placa',
            'moto_marca',
            'moto_modelo',
            'mecanico',
            'mecanico_nombre',
            'estado',
            'observaciones',
            'fecha_entrega',
            'venta',
            'venta_numero',
            'repuestos',
            'total',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'total']

    def get_total(self, obj: OrdenTaller):
        return obj.total_repuestos

    def create(self, validated_data):
        repuestos_data = validated_data.pop('repuestos', [])
        orden = OrdenTaller.objects.create(**validated_data)
        for repuesto_data in repuestos_data:
            OrdenRepuesto.objects.create(orden=orden, **repuesto_data)
        return orden

    def update(self, instance, validated_data):
        repuestos_data = validated_data.pop('repuestos', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if repuestos_data is not None:
            instance.repuestos.all().delete()
            for repuesto_data in repuestos_data:
                OrdenRepuesto.objects.create(orden=instance, **repuesto_data)
        return instance
