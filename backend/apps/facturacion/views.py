"""Endpoints de consulta para facturación electrónica."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.facturacion.exceptions import (
    DocumentoSoporteInvalido,
    DocumentoSoporteNoValido,
    FacturaNoValidaParaNotaCredito,
)
from apps.facturacion.models import (
    ConfiguracionDIAN,
    DocumentoSoporteElectronico,
    FacturaElectronica,
    NotaCreditoElectronica,
    RangoNumeracionDIAN,
)
from apps.facturacion.serializers import (
    ConfiguracionDIANSerializer,
    DocumentoSoporteCreateSerializer,
    DocumentoSoporteListSerializer,
    FacturaEstadoSerializer,
    NotaCreditoCreateSerializer,
    NotaCreditoListSerializer,
)
from apps.facturacion.serializers.factura_pos_serializer import FacturaPOSSerializer
from apps.facturacion.services import (
    DescargaFacturaError,
    DownloadResourceError,
    FacturaNoEncontrada,
    FactusConsultaError,
    FactusValidationError,
    download_pdf,
    download_remote_file,
    download_xml,
    emitir_documento_soporte,
    emitir_nota_ajuste_documento_soporte,
    emitir_nota_credito,
    read_local_media_file,
    sync_invoice_status,
)

logger = logging.getLogger(__name__)


def _is_legacy_download_response(request) -> bool:
    return str(request.query_params.get('legacy', '')).strip() in {'1', 'true', 'TRUE'}


def _build_file_response(content: bytes, filename: str, content_type: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


class FacturaElectronicaViewSet(viewsets.GenericViewSet):
    """ViewSet para consultar y sincronizar estado DIAN de facturas electrónicas."""

    permission_classes = [IsAuthenticated]
    serializer_class = FacturaEstadoSerializer

    def list(self, request):
        facturas = (
            FacturaElectronica.objects.select_related('venta__cliente')
            .order_by('-created_at')
        )
        data = [
            {
                'venta_id': factura.venta_id,
                'numero': factura.number,
                'reference_code': factura.reference_code,
                'cufe': factura.cufe,
                'uuid': factura.uuid,
                'cliente': factura.venta.cliente.nombre,
                'fecha': factura.venta.fecha,
                'total': factura.venta.total,
                'estado_dian': factura.status,
                'status': factura.status,
                'xml_url': factura.xml_url,
                'pdf_url': factura.pdf_url,
            }
            for factura in facturas
        ]
        return Response(data)

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/estado')
    def estado(self, request, number=None):
        try:
            factura = sync_invoice_status(number)
        except FacturaNoEncontrada as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except FactusConsultaError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        serializer = self.get_serializer(factura)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/xml')
    def xml(self, request, number=None):
        factura = FacturaElectronica.objects.filter(number=number).first()
        if factura is None:
            return Response(
                {'detail': f'No existe factura electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if _is_legacy_download_response(request):
            if not factura.xml_local_path:
                return Response(
                    {'detail': f'La factura {number} no tiene XML descargado localmente.'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({'numero': factura.number, 'xml': factura.xml_local_path})

        try:
            if factura.xml_local_path:
                content = read_local_media_file(factura.xml_local_path)
            else:
                if not factura.xml_url:
                    return Response(
                        {'detail': f'La factura {number} no tiene URL XML disponible.'},
                        status=status.HTTP_409_CONFLICT,
                    )
                local_path = download_xml(factura)
                content = read_local_media_file(local_path)
        except (DescargaFacturaError, DownloadResourceError) as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return _build_file_response(content, f'factura-{factura.number}.xml', 'application/xml')

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/pdf')
    def pdf(self, request, number=None):
        factura = FacturaElectronica.objects.filter(number=number).first()
        if factura is None:
            return Response(
                {'detail': f'No existe factura electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if _is_legacy_download_response(request):
            if not factura.pdf_local_path:
                return Response(
                    {'detail': f'La factura {number} no tiene PDF descargado localmente.'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({'numero': factura.number, 'pdf': factura.pdf_local_path})

        try:
            if factura.pdf_local_path:
                content = read_local_media_file(factura.pdf_local_path)
            else:
                if not factura.pdf_url:
                    return Response(
                        {'detail': f'La factura {number} no tiene URL PDF disponible.'},
                        status=status.HTTP_409_CONFLICT,
                    )
                local_path = download_pdf(factura)
                content = read_local_media_file(local_path)
        except (DescargaFacturaError, DownloadResourceError) as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return _build_file_response(content, f'factura-{factura.number}.pdf', 'application/pdf')

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/qr')
    def qr(self, request, number=None):
        factura = FacturaElectronica.objects.filter(number=number).first()
        if factura is None:
            return Response(
                {'detail': f'No existe factura electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not factura.qr:
            return Response(
                {'detail': f'La factura {number} no tiene QR generado.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({'numero': factura.number, 'qr': factura.qr.url})

    @action(detail=False, methods=['post'], url_path=r'(?P<number>[^/.]+)/enviar-correo')
    def enviar_correo(self, request, number=None):
        factura = FacturaElectronica.objects.select_related('venta__cliente').filter(number=number).first()
        if factura is None:
            return Response(
                {'detail': f'No existe factura electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        email_destino = factura.venta.cliente.email.strip()
        if not email_destino:
            return Response(
                {'detail': f'El cliente asociado a la factura {number} no tiene correo configurado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = f'Factura electrónica {factura.number}'
        message = (
            f'Hola {factura.venta.cliente.nombre},\n\n'
            f'Compartimos la información de tu factura electrónica {factura.number}.\n'
            f'Estado DIAN: {factura.status}\n'
            f'CUFE: {factura.cufe}\n\n'
            f'PDF: {factura.pdf_url}\n'
            f'XML: {factura.xml_url}\n\n'
            'Gracias por tu compra.'
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@lasafricanas.local')

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[email_destino],
                fail_silently=False,
            )
        except Exception:  # pragma: no cover - manejado por tests vía mock de excepciones
            logger.exception('Error enviando correo de factura número=%s', number)
            return Response(
                {'detail': 'No fue posible enviar la factura por correo en este momento.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'detail': f'Factura {factura.number} enviada a {email_destino}.'})

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/pos')
    def pos(self, request, number=None):
        factura = (
            FacturaElectronica.objects.select_related('venta__cliente')
            .prefetch_related('venta__detalles__producto')
            .filter(number=number)
            .first()
        )
        if factura is None:
            return Response(
                {'detail': f'No existe factura electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = FacturaPOSSerializer(factura)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='nota-credito')
    def nota_credito(self, request, pk=None):
        motivo = str(request.data.get('motivo', '')).strip()
        items = request.data.get('items', [])
        if not motivo:
            return Response({'detail': 'El campo motivo es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(items, list) or not items:
            return Response({'detail': 'El campo items debe ser una lista con al menos un elemento.'}, status=400)

        try:
            nota = emitir_nota_credito(factura_id=int(pk), motivo=motivo, items=items)
        except ValueError:
            return Response({'detail': 'factura_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        except FacturaElectronica.DoesNotExist as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except FacturaNoValidaParaNotaCredito as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'nota_credito': nota.number,
                'cufe': nota.cufe,
                'estado': nota.status,
            },
            status=status.HTTP_201_CREATED,
        )



    @action(detail=False, methods=['post'], url_path=r'documento-soporte/(?P<documento_soporte_id>[^/.]+)/nota-ajuste')
    def nota_ajuste_documento_soporte(self, request, documento_soporte_id=None):
        motivo = str(request.data.get('motivo', '')).strip()
        items = request.data.get('items', [])
        if not motivo:
            return Response({'detail': 'El campo motivo es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(items, list) or not items:
            return Response({'detail': 'El campo items debe ser una lista con al menos un elemento.'}, status=400)

        try:
            nota_ajuste = emitir_nota_ajuste_documento_soporte(documento_soporte_id=int(documento_soporte_id), motivo=motivo, items=items)
        except ValueError:
            return Response({'detail': 'documento_soporte_id inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        except DocumentoSoporteElectronico.DoesNotExist as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except DocumentoSoporteNoValido as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'nota_ajuste': nota_ajuste.number,
                'cufe': nota_ajuste.cufe,
                'estado': nota_ajuste.status,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='documento-soporte')
    def documento_soporte(self, request):
        try:
            documento = emitir_documento_soporte(request.data)
        except DocumentoSoporteInvalido as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'numero': documento.number,
                'cufe': documento.cufe,
                'estado': documento.status,
            },
            status=status.HTTP_201_CREATED,
        )


class ConfiguracionDIANViewSet(viewsets.GenericViewSet):
    """Endpoint para consultar y actualizar configuración DIAN del sistema."""

    permission_classes = [IsAuthenticated]
    serializer_class = ConfiguracionDIANSerializer

    def list(self, request):
        configuracion = ConfiguracionDIAN.objects.order_by('-created_at').first()
        if configuracion is None:
            return Response({}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(configuracion)
        return Response(serializer.data)

    def create(self, request):
        configuracion = ConfiguracionDIAN.objects.order_by('-created_at').first()
        if configuracion is None:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            rango_id = serializer.validated_data.get('rango_facturacion').id
            environment = (
                'PRODUCTION'
                if str(getattr(settings, 'FACTUS_ENV', 'sandbox')).strip().lower() in {'prod', 'production'}
                else 'SANDBOX'
            )
            RangoNumeracionDIAN.objects.filter(environment=environment, document_code='FACTURA_VENTA').update(
                is_selected_local=False
            )
            RangoNumeracionDIAN.objects.filter(pk=rango_id).update(is_selected_local=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer = self.get_serializer(configuracion, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        rango_id = serializer.validated_data.get('rango_facturacion').id
        environment = (
            'PRODUCTION'
            if str(getattr(settings, 'FACTUS_ENV', 'sandbox')).strip().lower() in {'prod', 'production'}
            else 'SANDBOX'
        )
        RangoNumeracionDIAN.objects.filter(environment=environment, document_code='FACTURA_VENTA').update(
            is_selected_local=False
        )
        RangoNumeracionDIAN.objects.filter(pk=rango_id).update(is_selected_local=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotasCreditoViewSet(viewsets.GenericViewSet):
    """Recursos REST para notas crédito electrónicas."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return NotaCreditoCreateSerializer
        return NotaCreditoListSerializer

    def list(self, request):
        queryset = NotaCreditoElectronica.objects.select_related('factura').order_by('-created_at')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            nota = emitir_nota_credito(
                factura_id=payload['factura_id'],
                motivo=payload['motivo'],
                items=payload['items'],
            )
        except FacturaElectronica.DoesNotExist as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except FacturaNoValidaParaNotaCredito as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output = NotaCreditoListSerializer(nota)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/xml')
    def xml(self, request, number=None):
        nota = NotaCreditoElectronica.objects.filter(number=number).first()
        if nota is None:
            return Response(
                {'detail': f'No existe nota crédito electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        xml = str(nota.xml_url or '').strip()
        if not xml:
            return Response(
                {'detail': f'La nota crédito {number} no tiene XML disponible.'},
                status=status.HTTP_409_CONFLICT,
            )
        if _is_legacy_download_response(request):
            return Response({'numero': nota.number, 'xml': xml})
        try:
            content = download_remote_file(xml)
        except DownloadResourceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'nota-credito-{nota.number}.xml', 'application/xml')

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/pdf')
    def pdf(self, request, number=None):
        nota = NotaCreditoElectronica.objects.filter(number=number).first()
        if nota is None:
            return Response(
                {'detail': f'No existe nota crédito electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        pdf = str(nota.pdf_url or '').strip()
        if not pdf:
            return Response(
                {'detail': f'La nota crédito {number} no tiene PDF disponible.'},
                status=status.HTTP_409_CONFLICT,
            )
        if _is_legacy_download_response(request):
            return Response({'numero': nota.number, 'pdf': pdf})
        try:
            content = download_remote_file(pdf)
        except DownloadResourceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'nota-credito-{nota.number}.pdf', 'application/pdf')


class DocumentosSoporteViewSet(viewsets.GenericViewSet):
    """Recursos REST para documentos soporte electrónicos."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentoSoporteCreateSerializer
        return DocumentoSoporteListSerializer

    def list(self, request):
        queryset = DocumentoSoporteElectronico.objects.order_by('-created_at')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            documento = emitir_documento_soporte(serializer.validated_data)
        except DocumentoSoporteInvalido as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        output = DocumentoSoporteListSerializer(documento)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/xml')
    def xml(self, request, number=None):
        documento = DocumentoSoporteElectronico.objects.filter(number=number).first()
        if documento is None:
            return Response(
                {'detail': f'No existe documento soporte electrónico para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        xml = str(documento.xml_url or '').strip()
        if not xml:
            return Response(
                {'detail': f'El documento soporte {number} no tiene XML disponible.'},
                status=status.HTTP_409_CONFLICT,
            )
        if _is_legacy_download_response(request):
            return Response({'numero': documento.number, 'xml': xml})
        try:
            content = download_remote_file(xml)
        except DownloadResourceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'documento-soporte-{documento.number}.xml', 'application/xml')

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/pdf')
    def pdf(self, request, number=None):
        documento = DocumentoSoporteElectronico.objects.filter(number=number).first()
        if documento is None:
            return Response(
                {'detail': f'No existe documento soporte electrónico para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        pdf = str(documento.pdf_url or '').strip()
        if not pdf:
            return Response(
                {'detail': f'El documento soporte {number} no tiene PDF disponible.'},
                status=status.HTTP_409_CONFLICT,
            )
        if _is_legacy_download_response(request):
            return Response({'numero': documento.number, 'pdf': pdf})
        try:
            content = download_remote_file(pdf)
        except DownloadResourceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'documento-soporte-{documento.number}.pdf', 'application/pdf')
