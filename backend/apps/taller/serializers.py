from rest_framework import serializers
from .models import Mecanico, ServicioMoto, RepuestoAsignado, ConsumoRepuesto
from apps.ventas.serializers import ClienteSerializer
from apps.inventario.serializers import ProductoListSerializer


class MecanicoSerializer(serializers.ModelSerializer):
    """Serializer para Mecánicos"""
    usuario_nombre = serializers.CharField(source='usuario.get_full_name', read_only=True)
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)
    total_cuentas = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    servicios_activos = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Mecanico
        fields = [
            'id',
            'usuario',
            'usuario_nombre',
            'usuario_username',
            'especialidad',
            'comision_porcentaje',
            'total_cuentas',
            'servicios_activos',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RepuestoAsignadoSerializer(serializers.ModelSerializer):
    """Serializer para repuestos asignados a mecánicos"""
    mecanico_nombre = serializers.CharField(source='mecanico.usuario.get_full_name', read_only=True)
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    valor_total = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = RepuestoAsignado
        fields = [
            'id',
            'mecanico',
            'mecanico_nombre',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'cantidad',
            'precio_unitario',
            'valor_total',
            'fecha_asignacion',
            'is_active'
        ]
        read_only_fields = ['fecha_asignacion']


class ConsumoRepuestoSerializer(serializers.ModelSerializer):
    """Serializer para consumos de repuestos en taller"""
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    registrado_por_nombre = serializers.CharField(source='registrado_por.username', read_only=True)
    
    class Meta:
        model = ConsumoRepuesto
        fields = [
            'id',
            'servicio',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'cantidad',
            'precio_unitario',
            'descuento',
            'subtotal',
            'registrado_por',
            'registrado_por_nombre',
            'descontado_de_mecanico',
            'stock_descontado',
            'created_at'
        ]
        read_only_fields = ['subtotal', 'descontado_de_mecanico', 'stock_descontado', 'created_at']


class ServicioMotoListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados de servicios"""
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    mecanico_nombre = serializers.CharField(source='mecanico.usuario.get_full_name', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = ServicioMoto
        fields = [
            'id',
            'numero_servicio',
            'placa',
            'marca',
            'modelo',
            'cliente',
            'cliente_nombre',
            'mecanico',
            'mecanico_nombre',
            'estado',
            'estado_display',
            'total',
            'fecha_ingreso',
            'fecha_estimada_entrega'
        ]


class ServicioMotoDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de servicio"""
    cliente_info = ClienteSerializer(source='cliente', read_only=True)
    mecanico_info = MecanicoSerializer(source='mecanico', read_only=True)
    recibido_por_nombre = serializers.CharField(source='recibido_por.get_full_name', read_only=True)
    consumos_repuestos = ConsumoRepuestoSerializer(many=True, read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = ServicioMoto
        fields = [
            'id',
            'numero_servicio',
            'placa',
            'marca',
            'modelo',
            'color',
            'cliente',
            'cliente_info',
            'mecanico',
            'mecanico_info',
            'recibido_por',
            'recibido_por_nombre',
            'fecha_ingreso',
            'fecha_estimada_entrega',
            'fecha_entrega_real',
            'kilometraje',
            'nivel_gasolina',
            'observaciones_ingreso',
            'diagnostico',
            'trabajo_realizado',
            'recomendaciones',
            'estado',
            'estado_display',
            'costo_mano_obra',
            'costo_repuestos',
            'descuento',
            'total',
            'venta',
            'consumos_repuestos',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'numero_servicio',
            'fecha_ingreso',
            'costo_repuestos',
            'total',
            'created_at',
            'updated_at'
        ]


class ServicioMotoCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear servicios"""
    
    class Meta:
        model = ServicioMoto
        fields = [
            'placa',
            'marca',
            'modelo',
            'color',
            'cliente',
            'mecanico',
            'recibido_por',
            'fecha_estimada_entrega',
            'kilometraje',
            'nivel_gasolina',
            'observaciones_ingreso',
            'diagnostico',
            'costo_mano_obra'
        ]
    
    def validate_placa(self, value):
        """Valida formato de placa"""
        return value.upper().strip()