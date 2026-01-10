from rest_framework import serializers
from .models import (
    ConfiguracionEmpresa,
    Impuesto,
    Auditoria,
    ConfiguracionFacturacion
)
from apps.usuarios.models import Usuario


class ConfiguracionEmpresaSerializer(serializers.ModelSerializer):
    """Serializer para configuración de empresa"""

    class Meta:
        model = ConfiguracionEmpresa
        fields = [
            'id',
            'tipo_identificacion',
            'identificacion',
            'dv',
            'tipo_persona',
            'razon_social',
            'regimen',
            'direccion',
            'ciudad',
            'municipio',
            'telefono',
            'sitio_web',
            'correo',
            'logo',
        ]


class ImpuestoSerializer(serializers.ModelSerializer):
    """Serializer para impuestos"""

    class Meta:
        model = Impuesto
        fields = [
            'id',
            'nombre',
            'valor',
            'porcentaje',
            'es_exento',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class AuditoriaSerializer(serializers.ModelSerializer):
    """Serializer para registros de auditoría"""

    class Meta:
        model = Auditoria
        fields = [
            'id',
            'fecha_hora',
            'usuario',
            'usuario_nombre',
            'accion',
            'modelo',
            'objeto_id',
            'notas',
            'ip_address',
        ]
        read_only_fields = ['fecha_hora']


class ConfiguracionFacturacionSerializer(serializers.ModelSerializer):
    """Serializer para configuración de facturación"""
    ultima_factura = serializers.SerializerMethodField()
    ultima_remision = serializers.SerializerMethodField()

    class Meta:
        model = ConfiguracionFacturacion
        fields = [
            'id',
            'prefijo_factura',
            'numero_factura',
            'ultima_factura',
            'prefijo_remision',
            'numero_remision',
            'ultima_remision',
            'resolucion',
            'notas_factura',
        ]

    def get_ultima_factura(self, obj):
        """Retorna el número de la última factura generada"""
        return max(0, obj.numero_factura - 1)

    def get_ultima_remision(self, obj):
        """Retorna el número de la última remisión generada"""
        return max(0, obj.numero_remision - 1)


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para usuarios del sistema"""
    nombre_completo = serializers.CharField(source='get_full_name', read_only=True)
    descuento_maximo = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'nombre_completo',
            'tipo_usuario',
            'telefono',
            'sede',
            'is_active',
            'date_joined',
            'descuento_maximo',
        ]
        read_only_fields = ['date_joined']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def get_descuento_maximo(self, obj):
        """Obtiene el descuento máximo del perfil de vendedor si existe"""
        if hasattr(obj, 'perfil_vendedor'):
            return float(obj.perfil_vendedor.descuento_maximo)
        return 0.0

    def create(self, validated_data):
        """Crear usuario con contraseña encriptada"""
        password = validated_data.pop('password', None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        """Actualizar usuario"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CambiarPasswordSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña"""
    clave_actual = serializers.CharField(required=True, write_only=True)
    clave_nueva = serializers.CharField(required=True, write_only=True)
    confirmar_clave = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        """Validar que las contraseñas nuevas coincidan"""
        if data['clave_nueva'] != data['confirmar_clave']:
            raise serializers.ValidationError({
                'confirmar_clave': 'Las contraseñas no coinciden'
            })

        if len(data['clave_nueva']) < 6:
            raise serializers.ValidationError({
                'clave_nueva': 'La contraseña debe tener al menos 6 caracteres'
            })

        return data

    def validate_clave_actual(self, value):
        """Validar que la contraseña actual sea correcta"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('La contraseña actual es incorrecta')
        return value
