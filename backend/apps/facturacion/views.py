"""Endpoints de consulta para facturación electrónica."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.facturacion.exceptions import (
    DocumentoSoporteInvalido,
    DocumentoSoporteNoValido,
    FacturaNoValidaParaNotaCredito,
)
from apps.facturacion.models import ConfiguracionDIAN, DocumentoSoporteElectronico, FacturaElectronica
from apps.facturacion.serializers import ConfiguracionDIANSerializer, FacturaEstadoSerializer
from apps.facturacion.serializers.factura_pos_serializer import FacturaPOSSerializer
from apps.facturacion.services import (
    FacturaNoEncontrada,
    FactusConsultaError,
    FactusValidationError,
    emitir_documento_soporte,
    emitir_nota_ajuste_documento_soporte,
    emitir_nota_credito,
    sync_invoice_status,
)

logger = logging.getLogger(__name__)


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
                'numero': factura.number,
                'cliente': factura.venta.cliente.nombre,
                'fecha': factura.venta.fecha,
                'total': factura.venta.total,
                'estado_dian': factura.status,
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
        if not factura.xml_local_path:
            return Response(
                {'detail': f'La factura {number} no tiene XML descargado localmente.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({'numero': factura.number, 'xml': factura.xml_local_path})

    @action(detail=False, methods=['get'], url_path=r'(?P<number>[^/.]+)/pdf')
    def pdf(self, request, number=None):
        factura = FacturaElectronica.objects.filter(number=number).first()
        if factura is None:
            return Response(
                {'detail': f'No existe factura electrónica para número {number}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not factura.pdf_local_path:
            return Response(
                {'detail': f'La factura {number} no tiene PDF descargado localmente.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response({'numero': factura.number, 'pdf': factura.pdf_local_path})

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
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer = self.get_serializer(configuracion, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
