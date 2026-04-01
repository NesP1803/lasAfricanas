import os
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImportJob, ImportFile, ImportProfile, ExportProfile, ExportJob
from .permissions import IsIntercambioAdmin
from .serializers import (
    ImportAnalyzeSerializer,
    ImportExecuteSerializer,
    ImportJobSerializer,
    ExportProfileSerializer,
    ExportGenerateSerializer,
)
from .services.orchestrator import analyze_file, execute_job, checksum_bytes
from .services.exporters.template_exporter import TEMPLATE_FIELDS, build_template
from .services.exporters.data_exporter import export_profile


class ImportacionesAnalyzeView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def post(self, request):
        serializer = ImportAnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile_id = serializer.validated_data.get('profile_id')
        profile = ImportProfile.objects.filter(id=profile_id).first() if profile_id else ImportProfile.objects.first()
        if not profile:
            profile = ImportProfile.objects.create(nombre='Default', codigo='default', precio_fuente='FINAL')

        job = ImportJob.objects.create(perfil=profile, usuario=request.user, estado='PENDIENTE')
        for f in serializer.validated_data['files']:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in {'.xlsx', '.xlsm', '.csv', '.xls', '.ods'}:
                return Response({'error': f'Formato no soportado: {ext}'}, status=400)
            content = f.read()
            import_file = ImportFile.objects.create(
                job=job,
                nombre=f.name,
                extension=ext,
                checksum=checksum_bytes(content),
                archivo=ContentFile(content, name=f.name),
            )
            analyze_file(import_file)
        job.estado = 'ANALIZADO'
        job.save(update_fields=['estado', 'updated_at'])
        return Response(ImportJobSerializer(job).data)


class ImportacionesExecuteView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def post(self, request):
        serializer = ImportExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = get_object_or_404(ImportJob, id=serializer.validated_data['job_id'])
        if job.estado != 'ANALIZADO':
            return Response({'error': 'El job debe estar analizado antes de ejecutar.'}, status=400)
        summary = execute_job(job)
        job.estado = 'EJECUTADO'
        job.resumen = summary
        job.save(update_fields=['estado', 'resumen', 'updated_at'])
        return Response({'job_id': job.id, 'summary': summary})


class ImportacionesListView(generics.ListAPIView):
    permission_classes = [IsIntercambioAdmin]
    serializer_class = ImportJobSerializer

    def get_queryset(self):
        return ImportJob.objects.prefetch_related('files__sheets').all()


class ImportacionesDetailView(generics.RetrieveAPIView):
    permission_classes = [IsIntercambioAdmin]
    serializer_class = ImportJobSerializer
    queryset = ImportJob.objects.prefetch_related('files__sheets', 'row_results').all()


class ImportacionesErroresView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def get(self, request, id):
        job = get_object_or_404(ImportJob, id=id)
        qs = job.row_results.filter(action__in=['ERROR', 'AMBIGUA', 'WARNING']).values('file__nombre', 'sheet__sheet_name', 'row_number', 'action', 'message')
        return Response(list(qs))


class ImportacionesReporteView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def get(self, request, id):
        job = get_object_or_404(ImportJob, id=id)
        return Response({'job': job.id, 'estado': job.estado, 'resumen': job.resumen, 'errores': job.errores, 'warnings': job.warnings})


class PlantillasListView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def get(self, request):
        return Response([{'codigo': code, 'columnas': cols} for code, cols in TEMPLATE_FIELDS.items()])


class PlantillasDownloadView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def get(self, request, codigo):
        if codigo not in TEMPLATE_FIELDS:
            return Response({'error': 'Plantilla no existe'}, status=404)
        payload = build_template(codigo)
        response = HttpResponse(payload, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=template_{codigo}.xlsx'
        return response


class ExportProfilesView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def get(self, request):
        if not ExportProfile.objects.exists():
            ExportProfile.objects.create(nombre='Exportación completa', codigo='full', entidades=['all'])
            ExportProfile.objects.create(nombre='Ventas + detalles', codigo='ventas_detalles', entidades=['ventas', 'detalles_venta'])
            ExportProfile.objects.create(nombre='Productos + proveedores', codigo='productos_proveedores', entidades=['productos', 'proveedores'])
            ExportProfile.objects.create(nombre='Clientes + motos', codigo='clientes_motos', entidades=['clientes', 'motos'])
        return Response(ExportProfileSerializer(ExportProfile.objects.all(), many=True).data)


class ExportGenerateView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def post(self, request):
        serializer = ExportGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_object_or_404(ExportProfile, codigo=serializer.validated_data['profile_code'])
        job = ExportJob.objects.create(perfil=profile, usuario=request.user)
        payload = export_profile(profile.codigo)
        filename = f'export_{profile.codigo}_{job.id}.xlsx'
        job.archivo.save(filename, ContentFile(payload), save=False)
        job.estado = 'GENERADO'
        job.resumen = {'profile': profile.codigo}
        job.save()
        return Response({'id': job.id, 'estado': job.estado})


class ExportDownloadView(APIView):
    permission_classes = [IsIntercambioAdmin]

    def get(self, request, id):
        job = get_object_or_404(ExportJob, id=id)
        if not job.archivo:
            return Response({'error': 'Archivo no generado'}, status=404)
        response = HttpResponse(job.archivo.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={os.path.basename(job.archivo.name)}'
        return response
