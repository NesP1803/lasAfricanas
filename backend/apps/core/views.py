from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import ConfiguracionEmpresa, ConfiguracionFacturacion, Impuesto, Auditoria
from .serializers import (
    ConfiguracionEmpresaSerializer,
    ConfiguracionFacturacionSerializer,
    ImpuestoSerializer,
    AuditoriaSerializer,
)


class ConfiguracionEmpresaViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracionEmpresa.objects.all()
    serializer_class = ConfiguracionEmpresaSerializer
    permission_classes = [IsAuthenticated]

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
            },
        )
        serializer = self.get_serializer([configuracion], many=True)
        return Response(serializer.data)


class ImpuestoViewSet(viewsets.ModelViewSet):
    queryset = Impuesto.objects.all()
    serializer_class = ImpuestoSerializer
    permission_classes = [IsAuthenticated]


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Auditoria.objects.all()
    serializer_class = AuditoriaSerializer
    permission_classes = [IsAuthenticated]
