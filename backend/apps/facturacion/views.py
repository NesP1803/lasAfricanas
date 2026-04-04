"""Endpoints de consulta para facturación electrónica."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from django.utils import timezone
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
    NotaCreditoPreviewSerializer,
)
from apps.facturacion.serializers.factura_pos_serializer import FacturaPOSSerializer
from apps.facturacion.services import (
    DescargaFacturaError,
    DownloadResourceError,
    FacturaNoEncontrada,
    FactusAPIError,
    FactusAuthError,
    FactusConsultaError,
    FactusPendingCreditNoteError,
    FactusValidationError,
    download_pdf,
    download_remote_file,
    download_xml,
    emitir_documento_soporte,
    emitir_nota_ajuste_documento_soporte,
    emitir_nota_credito,
    read_local_media_file,
    sync_numbering_ranges,
    sync_invoice_status,
    emitir_factura_completa,
    build_credit_preview,
    create_credit_note,
    sync_credit_note,
    CreditNoteValidationError,
    CreditNoteStateError,
)
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.electronic_state_machine import resolve_actions

logger = logging.getLogger(__name__)


def _is_admin(user) -> bool:
    return bool(
        user
        and (
            user.is_superuser
            or user.is_staff
            or getattr(user, 'tipo_usuario', None) == 'ADMIN'
        )
    )


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
        facturas = FacturaElectronica.objects.select_related('venta__cliente')
        estado_electronico = str(request.query_params.get('estado_electronico', '')).strip()
        if estado_electronico:
            facturas = facturas.filter(estado_electronico=estado_electronico)
        facturas = facturas.order_by('-created_at')
        data = [
            {
                'id': factura.id,
                'venta_id': factura.venta_id,
                'numero': factura.number,
                'reference_code': factura.reference_code,
                'cufe': factura.cufe,
                'uuid': factura.uuid,
                'cliente': factura.venta.cliente.nombre,
                'fecha': factura.venta.fecha,
                'total': factura.venta.total,
                'estado': factura.estado_electronico or factura.status,
                'estado_dian': factura.estado_electronico or factura.status,
                'status': factura.estado_electronico or factura.status,
                'estado_local': factura.venta.estado,
                'estado_electronico': factura.estado_electronico or factura.status,
                'acciones_sugeridas': resolve_actions(factura.estado_electronico or factura.status),
                'codigo_error': factura.codigo_error,
                'observaciones': factura.mensaje_error,
                'observaciones_json': factura.observaciones_json,
                'bill_errors': (
                    factura.response_json.get('bill_errors', [])
                    if isinstance(factura.response_json, dict)
                    else []
                ),
                'public_url': (
                    factura.public_url
                    or (
                        factura.response_json.get('final_fields', {}).get('public_url', '')
                        if isinstance(factura.response_json, dict)
                        else ''
                    )
                ),
                'qr_factus': factura.qr_data,
                'qr_image': factura.qr_image_url or factura.qr_image_data,
                'xml_url': factura.xml_url,
                'pdf_url': factura.pdf_url,
                'xml_local_path': factura.xml_local_path,
                'pdf_local_path': factura.pdf_local_path,
                'pdf_uploaded_to_factus': factura.pdf_uploaded_to_factus,
                'pdf_uploaded_at': factura.pdf_uploaded_at,
                'correo_enviado': factura.correo_enviado,
                'correo_enviado_at': factura.correo_enviado_at,
                'ultimo_error_correo': factura.ultimo_error_correo,
                'ultimo_error_pdf': factura.ultimo_error_pdf,
            }
            for factura in facturas
        ]
        return Response(data)

    def retrieve(self, request, pk=None):
        factura = (
            FacturaElectronica.objects.select_related('venta__cliente')
            .filter(pk=pk)
            .first()
        )
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacturaEstadoSerializer(factura).data)

    @action(detail=True, methods=['post'], url_path='sincronizar')
    def sincronizar(self, request, pk=None):
        factura = (
            FacturaElectronica.objects.select_related('venta__cliente')
            .filter(pk=pk)
            .first()
        )
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = emitir_factura_completa(factura.venta_id, triggered_by=request.user)
            sincronizada = result['factura']
        except FactusValidationError as exc:
            logger.warning(
                'facturacion.sincronizar.conflicto factura_id=%s venta_id=%s detail=%s',
                factura.id,
                factura.venta_id,
                str(exc),
            )
            return Response(
                {
                    'detail': str(exc),
                    'result': 'CONFLICT',
                },
                status=status.HTTP_409_CONFLICT,
            )
        except FactusConsultaError as exc:
            return Response({'detail': str(exc), 'result': 'REMOTE_ERROR'}, status=status.HTTP_502_BAD_GATEWAY)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc), 'result': 'REMOTE_ERROR'}, status=status.HTTP_502_BAD_GATEWAY)

        serializer = FacturaEstadoSerializer(sincronizada)
        return Response(
            {
                'detail': (
                    'Factura sincronizada y aceptada por DIAN.'
                    if (sincronizada.estado_electronico or sincronizada.status) in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}
                    else 'Factura reintentada/sincronizada, pero sigue en proceso en Factus/DIAN.'
                ),
                'result': 'SYNCED' if (sincronizada.estado_electronico or sincronizada.status) in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'} else 'PENDING',
                'factura': serializer.data,
                'warnings': result.get('warnings', []),
            }
        )

    @action(detail=True, methods=['get'], url_path='correo/contenido')
    def correo_contenido(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not factura.number:
            return Response({'detail': 'Factura sin número electrónico aún.'}, status=status.HTTP_409_CONFLICT)
        try:
            payload = FactusClient().get_invoice_email_content(factura.number)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(payload)

    @action(detail=True, methods=['post'], url_path='enviar-correo')
    def enviar_correo_factus(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not factura.number:
            return Response({'detail': 'Factura sin número electrónico aún.'}, status=status.HTTP_409_CONFLICT)
        email = str(request.data.get('email', '')).strip() or None
        try:
            payload = FactusClient().send_invoice_email(factura.number, email=email)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        factura.correo_enviado = True
        factura.correo_enviado_at = timezone.now()
        factura.ultimo_error_correo = ''
        factura.save(update_fields=['correo_enviado', 'correo_enviado_at', 'ultimo_error_correo', 'updated_at'])
        return Response({'detail': 'Correo enviado por Factus.', 'provider': payload})

    @action(detail=True, methods=['get'], url_path='eventos')
    def eventos(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not factura.number:
            return Response({'detail': 'Factura sin número electrónico aún.'}, status=status.HTTP_409_CONFLICT)
        try:
            payload = FactusClient().get_invoice_events(factura.number)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(payload)

    @action(detail=True, methods=['post'], url_path='aceptacion-tacita')
    def aceptacion_tacita(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not factura.number:
            return Response({'detail': 'Factura sin número electrónico aún.'}, status=status.HTTP_409_CONFLICT)
        try:
            payload = FactusClient().tacit_acceptance(factura.number)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'detail': 'Aceptación tácita ejecutada.', 'provider': payload})

    @action(detail=True, methods=['post'], url_path='eliminar')
    def eliminar(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not factura.number:
            return Response({'detail': 'Factura sin número electrónico aún.'}, status=status.HTTP_409_CONFLICT)
        if (factura.estado_electronico or factura.status) in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
            return Response(
                {'detail': 'No se permite eliminar localmente una factura aceptada para preservar trazabilidad.'},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            payload = FactusClient().delete_invoice(factura.number)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        factura.status = 'RECHAZADA'
        factura.estado_electronico = 'RECHAZADA'
        factura.mensaje_error = 'Documento eliminado/cancelado en Factus por acción administrativa.'
        factura.save(update_fields=['status', 'estado_electronico', 'mensaje_error', 'updated_at'])
        return Response({'detail': 'Eliminación solicitada en Factus.', 'provider': payload})

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

    @action(detail=True, methods=['get'], url_path='xml')
    def xml_by_id(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            if not factura.xml_local_path and factura.xml_url:
                download_xml(factura)
            content = read_local_media_file(factura.xml_local_path)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'factura-{factura.number}.xml', 'application/xml')

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf_by_id(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            if not factura.pdf_local_path and factura.pdf_url:
                download_pdf(factura)
            content = read_local_media_file(factura.pdf_local_path)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'factura-{factura.number}.pdf', 'application/pdf')

    @action(detail=True, methods=['post'], url_path='enviar_correo')
    def enviar_correo_by_id(self, request, pk=None):
        factura = FacturaElectronica.objects.select_related('venta__cliente').filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        result = emitir_factura_completa(factura.venta_id, triggered_by=request.user)
        factura.refresh_from_db()
        return Response(
            {
                'detail': 'Proceso de correo ejecutado.',
                'correo_enviado': factura.correo_enviado,
                'correo_enviado_at': factura.correo_enviado_at,
                'ultimo_error_correo': factura.ultimo_error_correo,
                'warnings': result.get('warnings', []),
            }
        )

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

    @action(detail=True, methods=['post'], url_path='notas-credito/preview')
    def notas_credito_preview(self, request, pk=None):
        factura = FacturaElectronica.objects.select_related('venta').filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = NotaCreditoPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = build_credit_preview(factura, serializer.validated_data['lines'])
        except (CreditNoteValidationError, CreditNoteStateError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Error inesperado generando preview de nota crédito para factura %s', factura.id)
            return Response({'detail': 'Error interno al generar preview de nota crédito.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(preview)

    @action(detail=True, methods=['post'], url_path='notas-credito/parcial')
    def notas_credito_parcial(self, request, pk=None):
        factura = FacturaElectronica.objects.select_related('venta').filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = NotaCreditoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            nota, meta = create_credit_note(
                factura=factura,
                motivo=data['motivo'],
                lines=data['lines'],
                is_total=False,
                user=request.user,
            )
        except (CreditNoteValidationError, CreditNoteStateError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusPendingCreditNoteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado creando nota crédito parcial para factura %s', factura.id)
            return Response({'detail': 'Error interno al crear nota crédito parcial.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        payload = NotaCreditoListSerializer(nota).data
        if meta.get('result') == 'factus_pending_manual_sync':
            payload['detail'] = (
                'Factus respondió conflicto 409, pero no se confirmó un documento remoto. '
                'La nota quedó en CONFLICTO_FACTUS; use "Sincronizar".'
            )
        elif meta.get('result') != 'created':
            payload['detail'] = 'Se detectó una nota crédito pendiente en Factus y se reconcilió automáticamente.'
        return Response(payload, status=int(meta.get('http_status', status.HTTP_201_CREATED)))

    @action(detail=True, methods=['post'], url_path='notas-credito/total')
    def notas_credito_total(self, request, pk=None):
        factura = FacturaElectronica.objects.select_related('venta').prefetch_related('venta__detalles').filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        motivo = str(request.data.get('motivo', 'Nota crédito total')).strip() or 'Nota crédito total'
        lines = [
            {
                'detalle_venta_original_id': d.id,
                'cantidad_a_acreditar': d.cantidad,
                'afecta_inventario': bool(request.data.get('afecta_inventario', True)),
                'motivo_linea': motivo,
            }
            for d in factura.venta.detalles.all()
        ]
        try:
            nota, meta = create_credit_note(
                factura=factura,
                motivo=motivo,
                lines=lines,
                is_total=True,
                user=request.user,
            )
        except (CreditNoteValidationError, CreditNoteStateError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusPendingCreditNoteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado creando nota crédito total para factura %s', factura.id)
            return Response({'detail': 'Error interno al crear nota crédito total.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        payload = NotaCreditoListSerializer(nota).data
        if meta.get('result') == 'factus_pending_manual_sync':
            payload['detail'] = (
                'Factus respondió conflicto 409, pero no se confirmó un documento remoto. '
                'La nota quedó en CONFLICTO_FACTUS; use "Sincronizar".'
            )
        elif meta.get('result') != 'created':
            payload['detail'] = 'Se detectó una nota crédito pendiente en Factus y se reconcilió automáticamente.'
        return Response(payload, status=int(meta.get('http_status', status.HTTP_201_CREATED)))



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

    @action(detail=False, methods=['get'], url_path='rangos')
    def rangos(self, request):
        environment = (
            'PRODUCTION'
            if str(getattr(settings, 'FACTUS_ENV', 'sandbox')).strip().lower() in {'prod', 'production'}
            else 'SANDBOX'
        )
        rangos = RangoNumeracionDIAN.objects.filter(
            environment=environment,
            document_code='FACTURA_VENTA',
        ).order_by('prefijo', 'factus_range_id')
        data = [
            {
                'id': rango.id,
                'factus_range_id': rango.factus_range_id,
                'environment': rango.environment,
                'document_code': rango.document_code,
                'document_name': 'Factura de venta',
                'prefix': rango.prefijo,
                'from_number': rango.desde,
                'to_number': rango.hasta,
                'current': rango.consecutivo_actual,
                'resolution_number': rango.resolucion,
                'technical_key': '',
                'is_active_remote': rango.is_active_remote,
                'is_selected_local': rango.is_selected_local,
            }
            for rango in rangos
        ]
        return Response(
            {
                'environment': environment,
                'document_code': 'FACTURA_VENTA',
                'selected_range_id': next((r['id'] for r in data if r['is_selected_local']), None),
                'ranges': data,
            }
        )

    @action(detail=False, methods=['post'], url_path='rangos/sync')
    def sync_ranges(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        synced = sync_numbering_ranges()
        return Response({'message': 'Rangos sincronizados correctamente.', 'count': len(synced)})

    @action(detail=False, methods=['post'], url_path='rangos/select')
    def select_range(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        rango_id = request.data.get('range_id')
        if not rango_id:
            return Response({'detail': 'Debe enviar range_id.'}, status=status.HTTP_400_BAD_REQUEST)
        environment = (
            'PRODUCTION'
            if str(getattr(settings, 'FACTUS_ENV', 'sandbox')).strip().lower() in {'prod', 'production'}
            else 'SANDBOX'
        )
        rango = RangoNumeracionDIAN.objects.filter(
            id=rango_id,
            environment=environment,
            document_code='FACTURA_VENTA',
        ).first()
        if rango is None:
            return Response({'detail': 'El rango no existe para el entorno actual.'}, status=status.HTTP_404_NOT_FOUND)

        RangoNumeracionDIAN.objects.filter(environment=environment, document_code='FACTURA_VENTA').update(
            is_selected_local=False
        )
        rango.is_selected_local = True
        rango.save(update_fields=['is_selected_local'])
        return Response({'message': 'Rango activo actualizado correctamente.', 'range_id': rango.id})

    def create(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
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
        factura_id = request.query_params.get('factura_id')
        if factura_id:
            queryset = queryset.filter(factura_id=factura_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.select_related('factura').prefetch_related('detalles').filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(NotaCreditoListSerializer(nota).data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        factura = FacturaElectronica.objects.select_related('venta').filter(pk=payload.get('factura_id')).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        lines = payload.get('lines') or payload.get('items') or []
        try:
            nota, meta = create_credit_note(
                factura=factura,
                motivo=payload['motivo'],
                lines=lines,
                is_total=False,
                user=request.user,
            )
        except (CreditNoteValidationError, CreditNoteStateError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusPendingCreditNoteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado creando nota crédito (endpoint legacy) para factura %s', factura.id)
            return Response({'detail': 'Error interno al crear nota crédito.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        output = NotaCreditoListSerializer(nota).data
        if meta.get('result') == 'factus_pending_manual_sync':
            output['detail'] = (
                'Factus respondió conflicto 409, pero no se confirmó un documento remoto. '
                'La nota quedó en CONFLICTO_FACTUS; use "Sincronizar".'
            )
        elif meta.get('result') != 'created':
            output['detail'] = 'Se detectó una nota crédito pendiente en Factus y se reconcilió automáticamente.'
        return Response(output, status=int(meta.get('http_status', status.HTTP_201_CREATED)))

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

    @action(detail=True, methods=['post'], url_path='sincronizar')
    def sincronizar(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            nota = sync_credit_note(nota)
        except (CreditNoteValidationError, CreditNoteStateError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusPendingCreditNoteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado sincronizando nota crédito %s', nota.id)
            return Response({'detail': 'Error interno al sincronizar la nota crédito.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(NotaCreditoListSerializer(nota).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf_by_id(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            from apps.facturacion.services.factus_client import FactusClient

            if nota.pdf_local_path:
                content = read_local_media_file(nota.pdf_local_path)
            else:
                content = FactusClient().download_credit_note_pdf(nota.number)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'nota-credito-{nota.number}.pdf', 'application/pdf')

    @action(detail=True, methods=['get'], url_path='xml')
    def xml_by_id(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            from apps.facturacion.services.factus_client import FactusClient

            if nota.xml_local_path:
                content = read_local_media_file(nota.xml_local_path)
            else:
                content = FactusClient().download_credit_note_xml(nota.number)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'nota-credito-{nota.number}.xml', 'application/xml')

    @action(detail=True, methods=['get'], url_path='correo/contenido')
    def correo_contenido(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        from apps.facturacion.services.factus_client import FactusClient

        payload = FactusClient().get_credit_note_email_content(nota.number)
        nota.email_content_json = payload
        nota.save(update_fields=['email_content_json', 'updated_at'])
        return Response(payload)

    @action(detail=True, methods=['post'], url_path='enviar-correo')
    def enviar_correo(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.select_related('factura__venta__cliente').filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        from apps.facturacion.services.factus_client import FactusClient

        email = str(request.data.get('email') or nota.factura.venta.cliente.email or '').strip()
        payload = {'email': email} if email else {}
        result = FactusClient().send_credit_note_email(nota.number, payload=payload)
        nota.correo_enviado = True
        nota.correo_enviado_at = timezone.now()
        nota.save(update_fields=['correo_enviado', 'correo_enviado_at', 'updated_at'])
        return Response(result)

    @action(detail=True, methods=['post'], url_path='eliminar')
    def eliminar(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if nota.estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
            return Response(
                {'detail': 'No se permite eliminar notas crédito aceptadas fiscalmente.'},
                status=status.HTTP_409_CONFLICT,
            )
        if nota.estado_local in {'BORRADOR', 'ERROR_INTEGRACION', 'ERROR_PERSISTENCIA', 'PENDIENTE_ENVIO'}:
            nota.estado_local = 'ANULADA_LOCAL'
            nota.deleted_at = timezone.now()
            nota.save(update_fields=['estado_local', 'deleted_at', 'updated_at'])
            return Response({'result': 'anulada_local', 'estado_local': nota.estado_local})
        return Response(
            {'detail': f'No se permite eliminar la nota en estado {nota.estado_local}.'},
            status=status.HTTP_409_CONFLICT,
        )

    def destroy(self, request, pk=None):
        return self.eliminar(request, pk=pk)


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
