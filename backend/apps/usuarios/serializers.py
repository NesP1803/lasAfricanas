from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Usuario

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Agregar información del usuario
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': 'admin' if self.user.is_superuser else 'vendedor',
        }
        
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'tipo_usuario',
            'telefono',
            'sede',
            'is_active',
            'last_login',
            'date_joined',
        ]
        read_only_fields = ['id', 'last_login', 'date_joined']
