from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import (
    ConfiguracionEmpresa,
    ConfiguracionFacturacion,
    Impuesto,
    Auditoria,
    AuditoriaArchivo,
)
from .serializers import (
    ConfiguracionEmpresaSerializer,
    ConfiguracionFacturacionSerializer,
    ImpuestoSerializer,
    AuditoriaSerializer,
)


class ConfiguracionEmpresaViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionEmpresa.objects.all()
    serializer_class = ConfiguracionEmpresaSerializer
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        configuracion, _ = ConfiguracionEmpresa.objects.get_or_create(
            id=1,
            defaults={
                'tipo_identificacion': 'NIT',
                'identificacion': '91068915',
                'dv': '8',
                'tipo_persona': 'Persona natural',
                'razon_social': 'MOTOREPUESTOS LAS AFRICANAS',
                'regimen': 'RÉGIMEN COMÚN',
                'direccion': 'CALLE 6 # 12A-45 GAIRA',
                'ciudad': 'MAGDALENA',
                'municipio': 'SANTA MARTA',
                'telefono': '54350548',
                'sitio_web': '',
                'correo': '',
            },
        )
        serializer = self.get_serializer([configuracion], many=True)
        return Response(serializer.data)


class ConfiguracionFacturacionViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionFacturacion.objects.all()
    serializer_class = ConfiguracionFacturacionSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        configuracion, _ = ConfiguracionFacturacion.objects.get_or_create(
            id=1,
            defaults={
                'prefijo_factura': 'FAC',
                'numero_factura': 1,
                'prefijo_remision': '',
                'numero_remision': 1,
                'resolucion': '',
                'notas_factura': '',
                'plantilla_factura_carta': '',
                'plantilla_factura_tirilla': '',
                'plantilla_remision_carta': '',
                'plantilla_remision_tirilla': '',
                'plantilla_nota_credito_carta': '',
                'plantilla_nota_credito_tirilla': '',
            },
        )
        serializer = self.get_serializer([configuracion], many=True)
        return Response(serializer.data)


class ImpuestoViewSet(viewsets.ModelViewSet):
    queryset = Impuesto.objects.all()
    serializer_class = ImpuestoSerializer
    permission_classes = [IsAuthenticated]

    def _ensure_default_impuestos(self):
        defaults = ['IVA 0%', 'IVA 19%', 'Exento']
        for nombre in defaults:
            Impuesto.objects.get_or_create(nombre=nombre)

    def list(self, request, *args, **kwargs):
        self._ensure_default_impuestos()
        return super().list(request, *args, **kwargs)


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Auditoria.objects.all()
    serializer_class = AuditoriaSerializer
    permission_classes = [IsAuthenticated]
    search_fields = [
        'usuario_nombre',
        'accion',
        'modelo',
        'objeto_id',
        'notas',
        'ip_address',
    ]
    ordering_fields = [
        'fecha_hora',
        'usuario_nombre',
        'accion',
        'modelo',
    ]
    ordering = ['-fecha_hora']
    filterset_fields = {
        'fecha_hora': ['gte', 'lte'],
        'accion': ['exact'],
        'usuario_nombre': ['exact', 'icontains'],
    }

    @action(detail=False, methods=['get'])
    def retention(self, request):
        return Response({
            'retention_days': getattr(settings, 'AUDITORIA_RETENTION_DAYS', 365),
            'archive_retention_days': getattr(
                settings, 'AUDITORIA_ARCHIVE_RETENTION_DAYS', 3650
            ),
        })

    @action(detail=False, methods=['post'])
    def archivar(self, request):
        if not (getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False)):
            return Response(
                {'detail': 'No autorizado para ejecutar esta acción.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        batch_size = int(request.data.get('batch_size', 1000))
        retention_days = getattr(settings, 'AUDITORIA_RETENTION_DAYS', 365)
        archive_retention_days = getattr(
            settings, 'AUDITORIA_ARCHIVE_RETENTION_DAYS', 3650
        )
        now = timezone.now()
        cutoff = now - timedelta(days=retention_days)
        archive_cutoff = now - timedelta(days=archive_retention_days)

        qs = Auditoria.objects.filter(fecha_hora__lt=cutoff).order_by('fecha_hora')
        total_to_archive = qs.count()
        archived_count = 0
        if total_to_archive:
            batch = []
            ids = []
            for registro in qs.iterator(chunk_size=batch_size):
                batch.append(
                    AuditoriaArchivo(
                        fecha_hora=registro.fecha_hora,
                        usuario=registro.usuario,
                        usuario_nombre=registro.usuario_nombre,
                        accion=registro.accion,
                        modelo=registro.modelo,
                        objeto_id=registro.objeto_id,
                        notas=registro.notas,
                        ip_address=registro.ip_address,
                    )
                )
                ids.append(registro.id)
                if len(batch) >= batch_size:
                    archived_count += self._flush_archivo(batch, ids)
                    batch, ids = [], []
            if batch:
                archived_count += self._flush_archivo(batch, ids)

        purged_count = 0
        if archive_retention_days > 0:
            purge_qs = AuditoriaArchivo.objects.filter(fecha_hora__lt=archive_cutoff)
            purged_count, _ = purge_qs.delete()

        return Response(
            {
                'archived': archived_count,
                'purged': purged_count,
                'total_to_archive': total_to_archive,
            }
        )

    @staticmethod
    def _flush_archivo(batch, ids):
        with transaction.atomic():
            AuditoriaArchivo.objects.bulk_create(batch)
            deleted, _ = Auditoria.objects.filter(id__in=ids).delete()
        return deleted
