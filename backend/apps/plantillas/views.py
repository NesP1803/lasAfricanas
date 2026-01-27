from __future__ import annotations

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DocumentType, OutputType, Template, TemplateVersion
from .serializers import (
    TemplateCreateSerializer,
    TemplateSerializer,
    TemplateVersionCreateSerializer,
    TemplateVersionSerializer,
)
from .services.context_builder import build_document_context
from .services.renderers import render_pdf, render_receipt, receipt_lines


class IsAdminUserType(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.tipo_usuario == 'ADMIN')


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.select_related('current_version')
    serializer_class = TemplateSerializer
    permission_classes = [IsAdminUserType]

    def get_queryset(self):
        queryset = super().get_queryset()
        document_type = self.request.query_params.get('document_type')
        output_type = self.request.query_params.get('output_type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        if output_type:
            queryset = queryset.filter(output_type=output_type)
        return queryset.order_by('name')

    def get_serializer_class(self):
        if self.action == 'create':
            return TemplateCreateSerializer
        return super().get_serializer_class()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            template = Template.objects.create(
                name=data['name'],
                document_type=data['document_type'],
                output_type=data['output_type'],
                is_active=data.get('is_active', False),
            )
            version = TemplateVersion.objects.create(
                template=template,
                version_number=1,
                html=data.get('html'),
                css=data.get('css'),
                receipt_text=data.get('receipt_text'),
                created_by=request.user,
                comment=data.get('comment', ''),
            )
            template.current_version = version
            template.save(update_fields=['current_version'])
            if template.is_active:
                Template.objects.filter(
                    document_type=template.document_type,
                    output_type=template.output_type,
                ).exclude(id=template.id).update(is_active=False)
        output_serializer = TemplateSerializer(template)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        template = self.get_object()
        current_version = template.current_version
        if not current_version:
            return Response(
                {"detail": "La plantilla no tiene versión actual."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            new_template = Template.objects.create(
                name=f"{template.name} (Copia)",
                document_type=template.document_type,
                output_type=template.output_type,
                is_active=False,
            )
            new_version = TemplateVersion.objects.create(
                template=new_template,
                version_number=1,
                html=current_version.html,
                css=current_version.css,
                receipt_text=current_version.receipt_text,
                created_by=request.user,
                comment=f"Copia de {template.name}",
            )
            new_template.current_version = new_version
            new_template.save(update_fields=['current_version'])
        return Response(TemplateSerializer(new_template).data)

    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        template = self.get_object()
        with transaction.atomic():
            Template.objects.filter(
                document_type=template.document_type,
                output_type=template.output_type,
            ).update(is_active=False)
            template.is_active = True
            template.save(update_fields=['is_active'])
        return Response({"detail": "Plantilla activada."})

    @action(detail=True, methods=['get', 'post'])
    def versions(self, request, pk=None):
        template = self.get_object()
        if request.method == 'GET':
            versions = template.versions.all().order_by('-version_number')
            serializer = TemplateVersionSerializer(versions, many=True)
            return Response(serializer.data)
        serializer = TemplateVersionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        next_version = (
            template.versions.values_list('version_number', flat=True).first() or 0
        ) + 1
        version = TemplateVersion.objects.create(
            template=template,
            version_number=next_version,
            html=data.get('html'),
            css=data.get('css'),
            receipt_text=data.get('receipt_text'),
            created_by=request.user,
            comment=data.get('comment', ''),
        )
        template.current_version = version
        template.save(update_fields=['current_version'])
        return Response(TemplateVersionSerializer(version).data, status=201)

    @action(detail=True, methods=['post'])
    def restore_version(self, request, pk=None):
        template = self.get_object()
        version_id = request.data.get('version_id')
        if not version_id:
            return Response(
                {"detail": "version_id es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        version = template.versions.filter(id=version_id).first()
        if not version:
            return Response(
                {"detail": "Versión no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        template.current_version = version
        template.save(update_fields=['current_version'])
        return Response({"detail": "Versión restaurada."})


class TemplatePreviewView(APIView):
    permission_classes = [IsAdminUserType]

    def post(self, request):
        document_type = request.data.get('document_type')
        output_type = request.data.get('output_type')
        template_version_id = request.data.get('template_version_id')
        document_id = request.data.get('document_id')

        if document_type not in DocumentType.values:
            return Response(
                {"detail": "Tipo de documento inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if output_type not in OutputType.values:
            return Response(
                {"detail": "Tipo de salida inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        version = None
        if template_version_id:
            version = TemplateVersion.objects.select_related('template').filter(
                id=template_version_id
            ).first()
        if not version:
            template = (
                Template.objects.filter(
                    document_type=document_type,
                    output_type=output_type,
                    is_active=True,
                )
                .select_related('current_version')
                .first()
            )
            version = template.current_version if template else None

        if not version:
            return Response(
                {"detail": "No se encontró una plantilla activa."},
                status=status.HTTP_404_NOT_FOUND,
            )

        context = build_document_context(document_type, document_id)

        if output_type == OutputType.PDF:
            pdf_bytes = render_pdf(version.html or "", version.css or "", context)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="preview.pdf"'
            return response

        rendered_text = render_receipt(version.receipt_text or "", context)
        return Response(
            {
                "template": version.receipt_text or "",
                "context": context,
                "rendered_lines": receipt_lines(rendered_text),
            }
        )


class DocumentPdfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, doc_type: str, document_id: int):
        template_version_id = request.query_params.get('template_version_id')
        if doc_type not in DocumentType.values:
            return Response(
                {"detail": "Tipo de documento inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        version = None
        if template_version_id:
            version = TemplateVersion.objects.filter(id=template_version_id).first()
        if not version:
            template = (
                Template.objects.filter(
                    document_type=doc_type,
                    output_type=OutputType.PDF,
                    is_active=True,
                )
                .select_related('current_version')
                .first()
            )
            version = template.current_version if template else None
        if not version:
            return Response(
                {"detail": "No se encontró una plantilla activa."},
                status=status.HTTP_404_NOT_FOUND,
            )
        context = build_document_context(doc_type, document_id)
        pdf_bytes = render_pdf(version.html or "", version.css or "", context)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="documento.pdf"'
        return response


class DocumentReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, doc_type: str, document_id: int):
        template_version_id = request.query_params.get('template_version_id')
        if doc_type not in DocumentType.values:
            return Response(
                {"detail": "Tipo de documento inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        version = None
        if template_version_id:
            version = TemplateVersion.objects.filter(id=template_version_id).first()
        if not version:
            template = (
                Template.objects.filter(
                    document_type=doc_type,
                    output_type=OutputType.RECEIPT,
                    is_active=True,
                )
                .select_related('current_version')
                .first()
            )
            version = template.current_version if template else None
        if not version:
            return Response(
                {"detail": "No se encontró una plantilla activa."},
                status=status.HTTP_404_NOT_FOUND,
            )
        context = build_document_context(doc_type, document_id)
        rendered_text = render_receipt(version.receipt_text or "", context)
        return Response(
            {
                "template": version.receipt_text or "",
                "context": context,
                "rendered_lines": receipt_lines(rendered_text),
            }
        )
