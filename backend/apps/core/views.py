from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
import subprocess
import os

from .models import ConfiguracionEmpresa, Impuesto, Auditoria, ConfiguracionFacturacion
from .serializers import (
    ConfiguracionEmpresaSerializer, ImpuestoSerializer, AuditoriaSerializer,
    ConfiguracionFacturacionSerializer, UsuarioSerializer, CambiarPasswordSerializer
)
from apps.usuarios.models import Usuario


def registrar_auditoria(usuario, accion, notas, modelo='', objeto_id='', request=None):
    """
    Función helper para registrar acciones en auditoría
    """
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')

    Auditoria.objects.create(
        usuario=usuario,
        usuario_nombre=usuario.username if usuario else 'Sistema',
        accion=accion,
        modelo=modelo,
        objeto_id=str(objeto_id),
        notas=notas,
        ip_address=ip_address
    )


class ConfiguracionEmpresaViewSet(viewsets.ModelViewSet):
    """ViewSet para configuración de empresa"""
    queryset = ConfiguracionEmpresa.objects.all()
    serializer_class = ConfiguracionEmpresaSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Retorna la configuración actual o crea una por defecto"""
        config = ConfiguracionEmpresa.objects.first()
        if not config:
            config = ConfiguracionEmpresa.objects.create(
                tipo_identificacion='NIT',
                identificacion='91068915',
                dv='8',
                tipo_persona='Persona natural',
                razon_social='MOTOREPUESTOS LAS AFRICANAS',
                regimen='RÉGIMEN COMÚN',
                direccion='CALLE 6 # 12A-45 GAIRA',
                ciudad='MAGDALENA',
                municipio='SANTA MARTA',
                telefono='54350548',
            )
        serializer = self.get_serializer(config)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """Actualizar configuración de empresa"""
        response = super().update(request, *args, **kwargs)
        registrar_auditoria(
            usuario=request.user,
            accion='ACTUALIZAR',
            notas=f'Actualización de datos de empresa: {request.data.get("razon_social", "")}',
            modelo='ConfiguracionEmpresa',
            objeto_id=kwargs.get('pk', ''),
            request=request
        )
        return response


class ImpuestoViewSet(viewsets.ModelViewSet):
    """ViewSet para impuestos"""
    queryset = Impuesto.objects.filter(is_active=True)
    serializer_class = ImpuestoSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Crear nuevo impuesto"""
        response = super().create(request, *args, **kwargs)
        registrar_auditoria(
            usuario=request.user,
            accion='CREAR',
            notas=f'Nuevo impuesto creado: {request.data.get("nombre", "")} - {request.data.get("valor", "")}',
            modelo='Impuesto',
            objeto_id=response.data.get('id', ''),
            request=request
        )
        return response

    def update(self, request, *args, **kwargs):
        """Actualizar impuesto"""
        response = super().update(request, *args, **kwargs)
        registrar_auditoria(
            usuario=request.user,
            accion='ACTUALIZAR',
            notas=f'Impuesto actualizado: {request.data.get("nombre", "")} - {request.data.get("valor", "")}',
            modelo='Impuesto',
            objeto_id=kwargs.get('pk', ''),
            request=request
        )
        return response

    def destroy(self, request, *args, **kwargs):
        """Eliminar impuesto (soft delete)"""
        instance = self.get_object()
        instance.soft_delete()
        registrar_auditoria(
            usuario=request.user,
            accion='ELIMINAR',
            notas=f'Impuesto eliminado: {instance.nombre} - {instance.valor}',
            modelo='Impuesto',
            objeto_id=instance.id,
            request=request
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para auditoría (solo lectura)"""
    queryset = Auditoria.objects.all()
    serializer_class = AuditoriaSerializer
    permission_classes = [IsAuthenticated]


class ConfiguracionFacturacionViewSet(viewsets.ModelViewSet):
    """ViewSet para configuración de facturación"""
    queryset = ConfiguracionFacturacion.objects.all()
    serializer_class = ConfiguracionFacturacionSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """Retorna la configuración actual o crea una por defecto"""
        config = ConfiguracionFacturacion.objects.first()
        if not config:
            config = ConfiguracionFacturacion.objects.create(
                prefijo_factura='FAC',
                numero_factura=100702,
                numero_remision=154239,
            )
        serializer = self.get_serializer(config)
        return Response(serializer.data)


class UsuarioViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de usuarios"""
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def desactivar(self, request, pk=None):
        """Desactivar usuario"""
        usuario = self.get_object()
        usuario.is_active = False
        usuario.save()
        registrar_auditoria(
            usuario=request.user,
            accion='ACTUALIZAR',
            notas=f'Usuario desactivado: {usuario.username}',
            modelo='Usuario',
            objeto_id=usuario.id,
            request=request
        )
        return Response({'status': 'usuario desactivado'})

    @action(detail=False, methods=['post'])
    def cambiar_password(self, request):
        """Cambiar contraseña del usuario actual"""
        serializer = CambiarPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['clave_nueva'])
        user.save()

        registrar_auditoria(
            usuario=user,
            accion='ACTUALIZAR',
            notas='Cambio de contraseña',
            modelo='Usuario',
            objeto_id=user.id,
            request=request
        )

        return Response({
            'status': 'success',
            'message': 'Contraseña cambiada exitosamente'
        })


class BackupViewSet(viewsets.ViewSet):
    """ViewSet para backup y restauración"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def crear_backup(self, request):
        """Crear backup de la base de datos"""
        try:
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'backup_{timestamp}.json')

            with open(backup_file, 'w') as f:
                subprocess.run(
                    ['python', 'manage.py', 'dumpdata', '--natural-foreign', '--natural-primary', '--indent', '2'],
                    stdout=f,
                    check=True,
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )

            registrar_auditoria(
                usuario=request.user,
                accion='OTRO',
                notas=f'Backup creado: {os.path.basename(backup_file)}',
                modelo='Sistema',
                request=request
            )

            return Response({
                'status': 'success',
                'message': 'Backup creado exitosamente',
                'archivo': os.path.basename(backup_file)
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Error al crear backup: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def listar_backups(self, request):
        """Listar backups disponibles"""
        try:
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')
            if not os.path.exists(backup_dir):
                return Response([])

            backups = []
            for file in os.listdir(backup_dir):
                if file.startswith('backup_') and file.endswith('.json'):
                    file_path = os.path.join(backup_dir, file)
                    stat = os.stat(file_path)
                    backups.append({
                        'nombre': file,
                        'fecha': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'tamaño': stat.st_size
                    })

            backups.sort(key=lambda x: x['fecha'], reverse=True)
            return Response(backups)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Error al listar backups: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
