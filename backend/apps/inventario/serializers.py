from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from rest_framework import serializers
from .models import Categoria, Proveedor, Producto, MovimientoInventario, ProductoFavorito


class CategoriaSerializer(serializers.ModelSerializer):
    """Serializer para Categorías"""
    total_productos = serializers.SerializerMethodField()
    
    class Meta:
        model = Categoria
        fields = [
            'id',
            'nombre',
            'descripcion',
            'orden',
            'is_active',
            'total_productos',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_total_productos(self, obj):
        """Cuenta cuántos productos tiene esta categoría"""
        return obj.productos.filter(is_active=True).count()


class ProveedorSerializer(serializers.ModelSerializer):
    """Serializer para Proveedores"""
    total_productos = serializers.SerializerMethodField()
    
    class Meta:
        model = Proveedor
        fields = [
            'id',
            'nombre',
            'nit',
            'telefono',
            'email',
            'direccion',
            'ciudad',
            'contacto',
            'is_active',
            'total_productos',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
        }
    
    def get_total_productos(self, obj):
        return obj.productos.filter(is_active=True).count()


class ProductoListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados de productos"""
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    stock_estado = serializers.SerializerMethodField()
    
    class Meta:
        model = Producto
        fields = [
            'id',
            'codigo',
            'nombre',
            'categoria',
            'categoria_nombre',
            'proveedor',
            'proveedor_nombre',
            'precio_venta',
            'stock',
            'unidad_medida',
            'stock_estado',
            'is_active',
            'created_at',
            'updated_at'
        ]
    
    def get_stock_estado(self, obj):
        """Indica el estado del stock"""
        if obj.stock <= 0:
            return 'AGOTADO'
        elif obj.stock_bajo:
            return 'BAJO'
        return 'OK'


class ProductoDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalle de producto"""
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    margen_utilidad = serializers.SerializerMethodField()
    valor_inventario = serializers.SerializerMethodField()
    stock_bajo = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Producto
        fields = [
            'id',
            'codigo',
            'nombre',
            'descripcion',
            'categoria',
            'categoria_nombre',
            'proveedor',
            'proveedor_nombre',
            'precio_costo',
            'precio_venta',
            'precio_venta_minimo',
            'stock',
            'stock_minimo',
            'stock_bajo',
            'unidad_medida',
            'iva_porcentaje',
            'iva_exento',
            'aplica_descuento',
            'es_servicio',
            'margen_utilidad',
            'valor_inventario',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def _format_decimal(self, value):
        if value is None:
            return None
        try:
            decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
            return str(decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def get_margen_utilidad(self, obj):
        return self._format_decimal(obj.margen_utilidad)

    def get_valor_inventario(self, obj):
        return self._format_decimal(obj.valor_inventario)


class ProductoCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar productos"""
    
    class Meta:
        model = Producto
        fields = [
            'codigo',
            'nombre',
            'descripcion',
            'categoria',
            'proveedor',
            'precio_costo',
            'precio_venta',
            'precio_venta_minimo',
            'stock',
            'stock_minimo',
            'unidad_medida',
            'iva_porcentaje',
            'iva_exento',
            'aplica_descuento',
            'es_servicio',
            'is_active'
        ]
    
    def validate_codigo(self, value):
        """Valida que el código sea único"""
        instance = self.instance
        if instance:
            # Actualización: permitir el mismo código
            if Producto.objects.exclude(pk=instance.pk).filter(codigo=value).exists():
                raise serializers.ValidationError("Ya existe un producto con este código")
        else:
            # Creación: código debe ser único
            if Producto.objects.filter(codigo=value).exists():
                raise serializers.ValidationError("Ya existe un producto con este código")
        return value

    def validate_unidad_medida(self, value):
        unidades_validas = {codigo for codigo, _ in Producto.UNIDADES_MEDIDA}
        if value not in unidades_validas:
            raise serializers.ValidationError(
                'Unidad de medida no válida. Use N/A, KG, LT o MT.'
            )
        return value
    
    def validate(self, data):
        """Validaciones generales"""
        if data.get('precio_venta_minimo', 0) > data.get('precio_venta', 0):
            raise serializers.ValidationError(
                "El precio de venta mínimo no puede ser mayor al precio de venta"
            )
        
        if data.get('precio_costo', 0) > data.get('precio_venta', 0):
            raise serializers.ValidationError(
                "El precio de costo no puede ser mayor al precio de venta"
            )

        unidad_medida = data.get('unidad_medida') or getattr(self.instance, 'unidad_medida', None)
        if unidad_medida == 'N/A':
            for field_name in ['stock', 'stock_minimo']:
                value = data.get(field_name)
                if value is None:
                    continue
                try:
                    decimal_value = Decimal(str(value))
                except (InvalidOperation, TypeError, ValueError):
                    raise serializers.ValidationError(
                        {field_name: 'La cantidad debe ser un número válido.'}
                    )
                if decimal_value != decimal_value.quantize(Decimal('1')):
                    raise serializers.ValidationError(
                        {field_name: 'Para unidad N/A solo se permiten enteros.'}
                    )
        
        return data


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    """Serializer para movimientos de inventario"""
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = MovimientoInventario
        fields = [
            'id',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'tipo',
            'tipo_display',
            'cantidad',
            'stock_anterior',
            'stock_nuevo',
            'costo_unitario',
            'usuario',
            'usuario_nombre',
            'referencia',
            'observaciones',
            'created_at'
        ]
        read_only_fields = ['created_at', 'stock_anterior', 'stock_nuevo']


class ProductoFavoritoSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_precio = serializers.DecimalField(
        source='producto.precio_venta',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    producto_stock = serializers.IntegerField(source='producto.stock', read_only=True)

    class Meta:
        model = ProductoFavorito
        fields = [
            'id',
            'producto',
            'producto_codigo',
            'producto_nombre',
            'producto_precio',
            'producto_stock',
            'alias',
            'orden',
            'created_at',
        ]
        read_only_fields = ['created_at']
