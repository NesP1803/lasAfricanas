from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import Usuario
from .serializers import UsuarioSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        if self.action == 'change_password':
            return [IsAuthenticated()]
        return [IsAdminUser()]

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
