from decimal import Decimal, InvalidOperation
from django.contrib.auth import authenticate
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Usuario
from .serializers import UsuarioSerializer


class IsAdminOrTipoAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser or getattr(user, 'tipo_usuario', None) == 'ADMIN')
        )


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'tipo_usuario', 'sede']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'date_joined', 'last_login']
    ordering = ['username']

    def get_permissions(self):
        if self.action == 'change_password':
            return [IsAuthenticated()]
        if self.action == 'me':
            return [IsAuthenticated()]
        if self.action == 'validar_descuento':
            return [IsAuthenticated()]
        return [IsAdminOrTipoAdmin()]

    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        if not request.user.is_superuser and request.user.id != int(pk):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'detail': 'La nueva contraseña es requerida.'}, status=status.HTTP_400_BAD_REQUEST)

        usuario = self.get_object()
        usuario.set_password(new_password)
        usuario.save(update_fields=['password'])

        return Response({'detail': 'Contraseña actualizada correctamente.'})

    @action(detail=False, methods=['post'])
    def validar_descuento(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        descuento_porcentaje = request.data.get('descuento_porcentaje')

        if not username or not password:
            return Response(
                {'detail': 'Usuario y contraseña son requeridos.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            descuento_decimal = Decimal(str(descuento_porcentaje))
        except (InvalidOperation, TypeError):
            return Response(
                {'detail': 'Descuento inválido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario = authenticate(request, username=username, password=password)
        if not usuario or not usuario.is_active:
            return Response({'detail': 'Credenciales inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

        aprobado = False
        if usuario.is_superuser or usuario.tipo_usuario == 'ADMIN':
            aprobado = True
        else:
            perfil = getattr(usuario, 'perfil_vendedor', None)
            if perfil and descuento_decimal <= perfil.descuento_maximo:
                aprobado = True

        if not aprobado:
            return Response(
                {'detail': 'El usuario no tiene permisos para aprobar este descuento.'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(
            {
                'id': usuario.id,
                'nombre': usuario.get_full_name() or usuario.username,
                'descuento_maximo': str(getattr(usuario, 'perfil_vendedor', None).descuento_maximo)
                if hasattr(usuario, 'perfil_vendedor')
                else None,
            }
        )

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        usuario = request.user

        if request.method.lower() == 'patch':
            allowed_fields = {
                'email',
                'first_name',
                'last_name',
                'telefono',
                'sede',
            }
            payload = {
                key: value
                for key, value in request.data.items()
                if key in allowed_fields
            }
            serializer = self.get_serializer(
                usuario, data=payload, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        serializer = self.get_serializer(usuario)
        return Response(serializer.data)
