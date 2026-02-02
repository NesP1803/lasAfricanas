from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Usuario

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # Agregar información del usuario
        role = 'ADMIN' if self.user.is_superuser else self.user.tipo_usuario
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': role,
            'es_cajero': self.user.es_cajero,
            'modulos_permitidos': self.user.modulos_permitidos,
        }

        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'tipo_usuario',
            'es_cajero',
            'telefono',
            'sede',
            'is_active',
            'password',
            'last_login',
            'date_joined',
            'modulos_permitidos',
        ]
        read_only_fields = ['id', 'last_login', 'date_joined']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)

        # Si no se especifica modulos_permitidos, asignar valor por defecto
        if 'modulos_permitidos' not in validated_data or validated_data.get('modulos_permitidos') is None:
            tipo_usuario = validated_data.get('tipo_usuario', 'VENDEDOR')
            # Para usuarios no-admin, asignar objeto vacío (solo tendrán acceso a Mi perfil)
            # Para admin, null significa acceso completo
            if tipo_usuario != 'ADMIN':
                validated_data['modulos_permitidos'] = {}

        usuario = Usuario(**validated_data)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
