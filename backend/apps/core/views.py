from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
import subprocess
import os
from datetime import datetime

from .models import (
    ConfiguracionEmpresa,
    Impuesto,
    Auditoria,
    ConfiguracionFacturacion
)
from .serializers import (
    ConfiguracionEmpresaSerializer,
    ImpuestoSerializer,
    AuditoriaSerializer,
    ConfiguracionFacturacionSerializer,
    UsuarioSerializer,
    CambiarPasswordSerializer
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
            # Crear configuración por defecto
            config = ConfiguracionEmpresa.objects.create(
                tipo_identificacion='NIT',
                identificacion='91068915',
                dv='8',
                tipo_persona='NATURAL',
                razon_social='MOTOREPUESTOS LAS AFRICANAS',
                regimen='COMUN',
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

    def get_queryset(self):
        """Filtrar auditorías"""
        queryset = super().get_queryset()
        # Filtros opcionales
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        usuario_id = self.request.query_params.get('usuario')
        accion = self.request.query_params.get('accion')

        if fecha_desde:
            queryset = queryset.filter(fecha_hora__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora__lte=fecha_hasta)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        if accion:
            queryset = queryset.filter(accion=accion)

        return queryset


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
                prefijo_remision='',
                numero_remision=154239,
                resolucion='18764006081459 de 2020/10/22\nRango del 00001 al 50000',
                notas_factura='Para trámite de cambios y garantías. Indispensable presentar la factura de venta.',
            )
        serializer = self.get_serializer(config)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """Actualizar configuración de facturación"""
        response = super().update(request, *args, **kwargs)
        registrar_auditoria(
            usuario=request.user,
            accion='ACTUALIZAR',
            notas='Actualización de configuración de facturación',
            modelo='ConfiguracionFacturacion',
            objeto_id=kwargs.get('pk', ''),
            request=request
        )
        return response


class UsuarioViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de usuarios"""
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtrar usuarios"""
        queryset = super().get_queryset()
        # Solo mostrar usuarios activos por defecto
        if self.request.query_params.get('incluir_inactivos') != 'true':
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('-date_joined')

    def create(self, request, *args, **kwargs):
        """Crear nuevo usuario"""
        response = super().create(request, *args, **kwargs)
        registrar_auditoria(
            usuario=request.user,
            accion='CREAR',
            notas=f'Nuevo usuario creado: {request.data.get("username", "")}',
            modelo='Usuario',
            objeto_id=response.data.get('id', ''),
            request=request
        )
        return response

    def update(self, request, *args, **kwargs):
        """Actualizar usuario"""
        response = super().update(request, *args, **kwargs)
        registrar_auditoria(
            usuario=request.user,
            accion='ACTUALIZAR',
            notas=f'Usuario actualizado: {request.data.get("username", "")}',
            modelo='Usuario',
            objeto_id=kwargs.get('pk', ''),
            request=request
        )
        return response

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

    @action(detail=True, methods=['post'])
    def activar(self, request, pk=None):
        """Activar usuario"""
        usuario = self.get_object()
        usuario.is_active = True
        usuario.save()
        registrar_auditoria(
            usuario=request.user,
            accion='ACTUALIZAR',
            notas=f'Usuario activado: {usuario.username}',
            modelo='Usuario',
            objeto_id=usuario.id,
            request=request
        )
        return Response({'status': 'usuario activado'})

    @action(detail=False, methods=['post'])
    def cambiar_password(self, request):
        """Cambiar contraseña del usuario actual"""
        serializer = CambiarPasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        # Cambiar contraseña
        user = request.user
        user.set_password(serializer.validated_data['clave_nueva'])
        user.save()

        registrar_auditoria(
            usuario=user,
            accion='ACTUALIZAR',
            notas=f'Cambio de contraseña',
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
            # Crear directorio de backups si no existe
            backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            # Nombre del archivo de backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'backup_{timestamp}.json')

            # Ejecutar dumpdata de Django
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
