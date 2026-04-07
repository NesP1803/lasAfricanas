"""Endpoints de consulta para facturación electrónica."""

import base64
import logging
from pathlib import Path

from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from django.db import transaction
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
    RemisionNumeracion,
    RemisionNumeracionHistorial,
    RangoNumeracionDIAN,
)
from apps.facturacion.serializers import (
    CreateRangoFactusSerializer,
    LocalRangoNumeracionSerializer,
    ConfiguracionDIANSerializer,
    DocumentoSoporteCreateSerializer,
    DocumentoSoporteListSerializer,
    FacturaEstadoSerializer,
    NotaCreditoCreateSerializer,
    NotaCreditoListSerializer,
    NotaCreditoPreviewSerializer,
    RangoNumeracionDIANSerializer,
    RemisionNumeracionHistorialSerializer,
    RemisionNumeracionSerializer,
    SelectActiveRangeSerializer,
    UpdateConsecutivoSerializer,
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
    download_remote_file,
    emitir_documento_soporte,
    emitir_nota_ajuste_documento_soporte,
    read_local_media_file,
    resolve_public_invoice_url,
    sync_numbering_ranges,
    sync_invoice_status,
    emitir_factura_completa,
    build_credit_preview,
    create_credit_note,
    sincronizar_nota_credito,
    sync_credit_note,
    sync_credit_note_with_effects,
    CreditNoteValidationError,
    CreditNoteStateError,
    get_invoice_email_content,
    send_invoice_email,
    delete_invoice_in_factus,
    create_range,
    delete_range,
    get_range,
    get_software_ranges_resilient,
    sync_ranges_to_db,
    update_range_current,
)
from apps.facturacion.services.factura_assets_service import sync_invoice_assets
from apps.facturacion.services.factus_client import FactusClient
from apps.facturacion.services.factus_environment import resolve_factus_environment
from apps.facturacion.services.electronic_state_machine import map_factus_status, resolve_actions
from apps.facturacion.services.public_invoice_url import has_documental_inconsistency

logger = logging.getLogger(__name__)

DOCUMENT_CODE_LABELS = {
    'FACTURA_VENTA': 'Factura de venta',
    'NOTA_CREDITO': 'Nota crédito',
    'DOCUMENTO_SOPORTE': 'Documento soporte',
    'NOTA_AJUSTE_DOCUMENTO_SOPORTE': 'Nota de ajuste documento soporte',
    'NOTA_DEBITO': 'Nota débito',
}


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


def _credit_note_http_status(meta: dict) -> int:
    return int(meta.get('http_status') or status.HTTP_200_OK)


def _credit_note_api_payload(nota, meta: dict) -> dict:
    payload = NotaCreditoListSerializer(nota).data
    payload.update({k: v for k, v in meta.items() if k != 'http_status'})
    return payload


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
                'estado': factura.estado_electronico,
                'estado_dian': factura.estado_electronico,
                'status': factura.estado_electronico,
                'estado_local': factura.venta.estado,
                'estado_electronico': factura.estado_electronico,
                'acciones_sugeridas': resolve_actions(factura.estado_electronico),
                'codigo_error': factura.codigo_error,
                'observaciones': factura.mensaje_error,
                'observaciones_json': factura.observaciones_json,
                'bill_errors': (
                    factura.response_json.get('bill_errors', [])
                    if isinstance(factura.response_json, dict)
                    else []
                ),
                'public_url': resolve_public_invoice_url(factura),
                'factus_public_url': resolve_public_invoice_url(factura),
                'documento_inconsistente': has_documental_inconsistency(factura),
                'mensaje_inconsistencia_documental': (
                    factura.mensaje_error if has_documental_inconsistency(factura) else ''
                ),
                'qr_factus': factura.qr_data,
                'qr_image': factura.qr_image_url or factura.qr_image_data,
                'xml_url': factura.xml_url,
                'pdf_url': factura.pdf_url,
                'xml_local_path': factura.xml_local_path,
                'pdf_local_path': factura.pdf_local_path,
                'email_subject': factura.email_subject,
                'email_zip_local_path': factura.email_zip_local_path,
                'send_email_enabled': factura.send_email_enabled,
                'last_assets_sync_at': factura.last_assets_sync_at,
                'can_sync_assets': bool(factura.number and (not factura.pdf_local_path or not factura.xml_local_path)),
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
                    if sincronizada.estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}
                    else 'Factura reintentada/sincronizada, pero sigue en proceso en Factus/DIAN.'
                ),
                'result': 'SYNCED' if sincronizada.estado_electronico in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'} else 'PENDING',
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
        save_zip = str(request.query_params.get('save_zip', '')).strip().lower() in {'1', 'true', 'yes', 'si', 'sí'}
        try:
            payload = get_invoice_email_content(factura=factura, save_zip=save_zip)
        except (FactusAPIError, FactusAuthError, FactusValidationError, DescargaFacturaError) as exc:
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
        pdf_base_64_encoded = str(request.data.get('pdf_base_64_encoded', '')).strip() or None
        try:
            payload = send_invoice_email(factura=factura, email=email, pdf_base_64_encoded=pdf_base_64_encoded)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (FactusAPIError, FactusAuthError) as exc:
            factura.ultimo_error_correo = str(exc)[:500]
            factura.save(update_fields=['ultimo_error_correo', 'updated_at'])
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
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
        try:
            payload = delete_invoice_in_factus(factura=factura)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
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
                sync_invoice_assets(factura, include_email_content=False)
                local_path = factura.xml_local_path
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
                sync_invoice_assets(factura, include_email_content=False)
                local_path = factura.pdf_local_path
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
            f'Estado DIAN: {factura.estado_electronico}\n'
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
            if not factura.xml_local_path:
                sync_invoice_assets(factura, include_email_content=False)
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
            if not factura.pdf_local_path:
                sync_invoice_assets(factura, include_email_content=False)
            content = read_local_media_file(factura.pdf_local_path)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return _build_file_response(content, f'factura-{factura.number}.pdf', 'application/pdf')

    @action(detail=True, methods=['post'], url_path='enviar-correo')
    def enviar_correo_by_id(self, request, pk=None):
        factura = FacturaElectronica.objects.select_related('venta__cliente').filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not factura.number:
            return Response({'detail': 'Factura sin número Factus aún.'}, status=status.HTTP_409_CONFLICT)

        email_destino = str(request.data.get('email') or getattr(factura.venta.cliente, 'email', '') or '').strip()
        if not email_destino:
            return Response({'detail': 'El cliente no tiene correo configurado.'}, status=status.HTTP_400_BAD_REQUEST)
        pdf_base64 = None
        if factura.pdf_local_path:
            try:
                absolute_pdf = Path(settings.MEDIA_ROOT) / factura.pdf_local_path
                pdf_base64 = base64.b64encode(absolute_pdf.read_bytes()).decode('utf-8')
            except Exception:
                pdf_base64 = None
        try:
            provider = FactusClient().send_bill_email(factura.number, email_destino, pdf_base_64_encoded=pdf_base64)
            factura.correo_enviado = True
            factura.correo_enviado_at = timezone.now()
            factura.email_sent_at = factura.correo_enviado_at
            factura.ultimo_error_correo = ''
            factura.email_last_error = ''
            factura.response_json = {**(factura.response_json or {}), 'send_email_response': provider}
            factura.save(
                update_fields=[
                    'correo_enviado',
                    'correo_enviado_at',
                    'email_sent_at',
                    'ultimo_error_correo',
                    'email_last_error',
                    'response_json',
                    'updated_at',
                ]
            )
        except (FactusAPIError, FactusAuthError, FactusValidationError) as exc:
            factura.ultimo_error_correo = str(exc)[:500]
            factura.email_last_error = factura.ultimo_error_correo
            factura.save(update_fields=['ultimo_error_correo', 'email_last_error', 'updated_at'])
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(
            {
                'detail': 'Correo enviado por Factus.',
                'correo_enviado': factura.correo_enviado,
                'correo_enviado_at': factura.correo_enviado_at,
                'ultimo_error_correo': factura.ultimo_error_correo,
                'provider': provider,
            }
        )

    @action(detail=True, methods=['post'], url_path='sincronizar-archivos')
    def sincronizar_archivos(self, request, pk=None):
        factura = FacturaElectronica.objects.filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        include_email_content = str(request.data.get('include_email_content', '')).strip().lower() in {'1', 'true', 'yes', 'si', 'sí'}
        force = str(request.data.get('force', '')).strip().lower() in {'1', 'true', 'yes'}
        try:
            result = sync_invoice_assets(
                factura,
                include_email_content=include_email_content,
                force=force,
            )
        except (FactusAPIError, FactusAuthError, DescargaFacturaError, FactusValidationError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(result)

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

        factura = FacturaElectronica.objects.select_related('venta').filter(pk=pk).first()
        if factura is None:
            return Response({'detail': 'Factura electrónica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            nota, meta = create_credit_note(
                factura=factura,
                motivo=motivo,
                lines=items,
                is_total=False,
                user=request.user,
            )
        except (CreditNoteValidationError, CreditNoteStateError, FacturaNoValidaParaNotaCredito) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(_credit_note_api_payload(nota, meta), status=_credit_note_http_status(meta))

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
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado creando nota crédito parcial para factura %s', factura.id)
            return Response({'detail': 'Error interno al crear nota crédito parcial.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(_credit_note_api_payload(nota, meta), status=_credit_note_http_status(meta))

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
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado creando nota crédito total para factura %s', factura.id)
            return Response({'detail': 'Error interno al crear nota crédito total.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(_credit_note_api_payload(nota, meta), status=_credit_note_http_status(meta))



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
            documento = emitir_documento_soporte(request.data, user=request.user)
        except DocumentoSoporteInvalido as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (FactusAPIError, FactusAuthError) as exc:
            if isinstance(exc, FactusAPIError) and int(getattr(exc, 'status_code', 0) or 0) == 409:
                return Response(
                    {
                        'detail': str(exc),
                        'result': 'PENDING_DIAN_CONFLICT',
                        'warning': 'Existe un documento soporte en proceso DIAN en Factus. Sincronice y reintente.',
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

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
        environment = resolve_factus_environment()
        document_code = str(request.query_params.get('document_code', 'FACTURA_VENTA')).strip().upper() or 'FACTURA_VENTA'
        valid_codes = {choice[0] for choice in RangoNumeracionDIAN.DOCUMENT_CODE_CHOICES}
        if document_code not in valid_codes:
            return Response({'detail': 'document_code no soportado.'}, status=status.HTTP_400_BAD_REQUEST)
        rangos = RangoNumeracionDIAN.objects.filter(
            environment=environment,
            document_code=document_code,
        ).order_by('prefijo', 'factus_range_id')
        data = [
            {
                'id': rango.id,
                'factus_range_id': rango.factus_range_id,
                'environment': rango.environment,
                'document_code': rango.document_code,
                'document_name': DOCUMENT_CODE_LABELS.get(rango.document_code, rango.document_code),
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
                'document_code': document_code,
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
        document_code = str(request.data.get('document_code', 'FACTURA_VENTA')).strip().upper() or 'FACTURA_VENTA'
        if not rango_id:
            return Response({'detail': 'Debe enviar range_id.'}, status=status.HTTP_400_BAD_REQUEST)
        valid_codes = {choice[0] for choice in RangoNumeracionDIAN.DOCUMENT_CODE_CHOICES}
        if document_code not in valid_codes:
            return Response({'detail': 'document_code no soportado.'}, status=status.HTTP_400_BAD_REQUEST)
        environment = resolve_factus_environment()
        rango = RangoNumeracionDIAN.objects.filter(
            id=rango_id,
            environment=environment,
            document_code=document_code,
        ).first()
        if rango is None:
            return Response({'detail': 'El rango no existe para el entorno actual.'}, status=status.HTTP_404_NOT_FOUND)

        RangoNumeracionDIAN.objects.filter(environment=environment, document_code=document_code).update(
            is_selected_local=False
        )
        rango.is_selected_local = True
        rango.save(update_fields=['is_selected_local'])
        return Response(
            {
                'message': 'Rango activo actualizado correctamente.',
                'note': (
                    'El cambio de rango DIAN aplica únicamente a nuevas emisiones. '
                    'No altera uuid/cufe/number históricos ya emitidos.'
                ),
                'range_id': rango.id,
                'document_code': document_code,
                'environment': environment,
            }
        )

    @action(detail=False, methods=['get'], url_path='health')
    def factus_health(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        client = FactusClient()
        try:
            result = client.health_check()
        except (FactusAPIError, FactusAuthError) as exc:
            return Response(
                {
                    'environment': client.get_effective_environment(),
                    'base_url': client.base_url,
                    'detail': str(exc),
                    'healthy': False,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                **result,
                'healthy': bool(result.get('has_credentials') and result.get('token_ok') and result.get('numbering_ranges_ok')),
            }
        )

    def create(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        configuracion = ConfiguracionDIAN.objects.order_by('-created_at').first()
        if configuracion is None:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            rango_id = serializer.validated_data.get('rango_facturacion').id
            environment = resolve_factus_environment()
            RangoNumeracionDIAN.objects.filter(environment=environment, document_code='FACTURA_VENTA').update(
                is_selected_local=False
            )
            RangoNumeracionDIAN.objects.filter(pk=rango_id).update(is_selected_local=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer = self.get_serializer(configuracion, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # El cambio de rango seleccionado actualiza solo la configuración para futuras emisiones.
        # Los campos locales/visuales (ej. FAC-1 / REM-1) no reemplazan identificadores electrónicos
        # históricos (number, uuid, cufe) de documentos ya emitidos.
        rango_id = serializer.validated_data.get('rango_facturacion').id
        environment = resolve_factus_environment()
        RangoNumeracionDIAN.objects.filter(environment=environment, document_code='FACTURA_VENTA').update(
            is_selected_local=False
        )
        RangoNumeracionDIAN.objects.filter(pk=rango_id).update(is_selected_local=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FacturacionRangosViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    MAIN_DOCUMENT_CODES = {'FACTURA_VENTA', 'NOTA_CREDITO', 'DOCUMENTO_SOPORTE'}

    def _base_queryset(self):
        environment = resolve_factus_environment()
        return RangoNumeracionDIAN.objects.filter(environment=environment).order_by('-created_at', '-id')

    def list(self, request):
        queryset = self._base_queryset()
        document_code = str(request.query_params.get('document_code', '')).strip().upper()
        if document_code:
            queryset = queryset.filter(document_code=document_code)
        else:
            queryset = queryset.filter(document_code__in=self.MAIN_DOCUMENT_CODES)
        estado = str(request.query_params.get('estado', '')).strip().lower()
        if estado == 'activo':
            queryset = queryset.filter(activo=True, is_expired_remote=False)
        elif estado == 'inactivo':
            queryset = queryset.filter(activo=False)
        elif estado == 'vencido':
            queryset = queryset.filter(is_expired_remote=True)
        elif estado == 'seleccionado':
            queryset = queryset.filter(is_selected_local=True)
        prefijo = str(request.query_params.get('prefijo', '')).strip()
        if prefijo:
            queryset = queryset.filter(prefijo__icontains=prefijo)
        resolucion = str(request.query_params.get('resolucion', '')).strip()
        if resolucion:
            queryset = queryset.filter(resolucion__icontains=resolucion)
        serializer = RangoNumeracionDIANSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='sync')
    def sync(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        synced = sync_ranges_to_db()
        return Response({'message': 'Rangos sincronizados correctamente.', 'count': len(synced)})

    def retrieve(self, request, pk=None):
        rango = self._base_queryset().filter(pk=pk).first()
        if not rango:
            return Response({'detail': 'Rango no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        payload = get_range(int(rango.factus_id or rango.factus_range_id or 0))
        return Response(
            {
                'local': RangoNumeracionDIANSerializer(rango).data,
                'remote': payload,
            }
        )

    def create(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        payload = dict(request.data)
        payload['environment'] = resolve_factus_environment()
        activate_now = str(payload.get('activate_now', '')).strip().lower() in {'1', 'true', 'si', 'sí', 'yes'}
        serializer = LocalRangoNumeracionSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            rango = serializer.save(
                environment=resolve_factus_environment(),
                document_name=DOCUMENT_CODE_LABELS.get(serializer.validated_data['document_code'], ''),
                is_selected_local=activate_now,
            )
            if activate_now:
                self._base_queryset().filter(document_code=rango.document_code).exclude(pk=rango.pk).update(is_selected_local=False)
        return Response(RangoNumeracionDIANSerializer(rango).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        rango = self._base_queryset().filter(pk=pk).first()
        if not rango:
            return Response({'detail': 'Rango no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = LocalRangoNumeracionSerializer(instance=rango, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        rango = serializer.save()
        return Response(RangoNumeracionDIANSerializer(rango).data)

    @action(detail=True, methods=['patch'], url_path='consecutivo')
    def consecutivo(self, request, pk=None):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        rango = self._base_queryset().filter(pk=pk).first()
        if not rango:
            return Response({'detail': 'Rango no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = UpdateConsecutivoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_current = serializer.validated_data['current']
        if new_current < rango.desde or new_current > rango.hasta:
            return Response({'detail': 'El consecutivo está fuera del rango permitido.'}, status=status.HTTP_400_BAD_REQUEST)
        payload = update_range_current(int(rango.factus_id or rango.factus_range_id), new_current)
        if serializer.validated_data.get('sync_local', True):
            rango.consecutivo_actual = new_current
            rango.last_synced_at = timezone.now()
            rango.save(update_fields=['consecutivo_actual', 'last_synced_at'])
        return Response({'message': 'Consecutivo actualizado.', 'provider': payload, 'range': RangoNumeracionDIANSerializer(rango).data})

    def destroy(self, request, pk=None):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        rango = self._base_queryset().filter(pk=pk).first()
        if not rango:
            return Response({'detail': 'Rango no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        payload = {}
        if rango.factus_id or rango.factus_range_id:
            try:
                payload = delete_range(int(rango.factus_id or rango.factus_range_id))
            except Exception:
                payload = {}
        rango.delete()
        return Response({'message': 'Rango eliminado.', 'provider': payload})

    @action(detail=False, methods=['get'], url_path='software')
    def software(self, request):
        software_status = get_software_ranges_resilient()
        software_ranges = software_status['ranges']
        document = str(request.query_params.get('document', '')).strip()
        allowed_documents = {'21', '22', '24'}
        if document in allowed_documents:
            software_ranges = [item for item in software_ranges if str(item.get('document')) == document]
        else:
            software_ranges = [item for item in software_ranges if str(item.get('document')) in allowed_documents]
        local_by_id = {int(item.factus_id or item.factus_range_id or 0): item for item in self._base_queryset()}
        comparisons = []
        for item in software_ranges:
            factus_id = int(item.get('id') or item.get('numbering_range_id') or 0)
            local = local_by_id.get(factus_id)
            comparisons.append(
                {
                    'remote': item,
                    'local_match': RangoNumeracionDIANSerializer(local).data if local else None,
                    'matches_local': bool(local),
                    'differences': [] if not local else _compare_software_vs_local(item, local),
                }
            )
        return Response(
            {
                'status': 'degraded' if software_status['degraded'] else 'ok',
                'detail': software_status['error'],
                'items': comparisons,
            }
        )

    @action(detail=True, methods=['patch'], url_path='seleccionar-activo')
    def seleccionar_activo(self, request, pk=None):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SelectActiveRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_code = serializer.validated_data['document_code']
        rango = self._base_queryset().filter(pk=pk, document_code=document_code).first()
        if not rango:
            return Response({'detail': 'Rango no encontrado para el tipo documental indicado.'}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            self._base_queryset().filter(document_code=document_code).update(is_selected_local=False)
            rango.is_selected_local = True
            rango.save(update_fields=['is_selected_local'])
        return Response({'message': 'Rango seleccionado localmente.', 'range': RangoNumeracionDIANSerializer(rango).data})

    @action(detail=True, methods=['patch'], url_path='activar')
    def activar(self, request, pk=None):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        rango = self._base_queryset().filter(pk=pk).first()
        if not rango:
            return Response({'detail': 'Rango no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        enabled = bool(request.data.get('activo', True))
        rango.activo = enabled
        if not enabled and rango.is_selected_local:
            rango.is_selected_local = False
            rango.save(update_fields=['activo', 'is_selected_local'])
        else:
            rango.save(update_fields=['activo'])
        return Response({'message': 'Estado actualizado.', 'range': RangoNumeracionDIANSerializer(rango).data})


def _compare_software_vs_local(remote: dict, local: RangoNumeracionDIAN) -> list[str]:
    differences: list[str] = []
    pairs = [
        ('prefix', local.prefijo, str(remote.get('prefix') or '')),
        ('from', local.desde, int(remote.get('from') or local.desde)),
        ('to', local.hasta, int(remote.get('to') or local.hasta)),
        ('resolution_number', local.resolucion, str(remote.get('resolution_number') or '')),
        ('technical_key', local.technical_key, str(remote.get('technical_key') or '')),
    ]
    for field, local_value, remote_value in pairs:
        if local_value != remote_value:
            differences.append(field)
    return differences


class RemisionesNumeracionViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='numeracion')
    def numeracion(self, request):
        numeracion = RemisionNumeracion.objects.order_by('-updated_at').first()
        if not numeracion:
            return Response({})
        return Response(RemisionNumeracionSerializer(numeracion).data)

    @numeracion.mapping.patch
    def actualizar_numeracion(self, request):
        if not _is_admin(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        instance = RemisionNumeracion.objects.order_by('-updated_at').first()
        previous = RemisionNumeracionSerializer(instance).data if instance else {}
        serializer = RemisionNumeracionSerializer(instance=instance, data=request.data, partial=bool(instance))
        serializer.is_valid(raise_exception=True)
        numeracion = serializer.save(updated_by=request.user)
        RemisionNumeracionHistorial.objects.create(
            numeracion=numeracion,
            previous_data=previous,
            new_data=RemisionNumeracionSerializer(numeracion).data,
            changed_by=request.user,
        )
        return Response(RemisionNumeracionSerializer(numeracion).data)

    @action(detail=False, methods=['get'], url_path='historial')
    def historial(self, request):
        queryset = RemisionNumeracionHistorial.objects.select_related('changed_by', 'numeracion')[:100]
        return Response(RemisionNumeracionHistorialSerializer(queryset, many=True).data)


class NotasCreditoViewSet(viewsets.GenericViewSet):
    """Recursos REST para notas crédito electrónicas."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return NotaCreditoCreateSerializer
        return NotaCreditoListSerializer

    def _auto_sync_if_needed(self, nota: NotaCreditoElectronica, *, user) -> NotaCreditoElectronica:
        if nota.estado_local not in {'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'}:
            return nota
        last_sync = nota.last_sync_at or nota.synchronized_at
        if last_sync and (timezone.now() - last_sync).total_seconds() < 30:
            return nota
        try:
            nota, _ = sync_credit_note_with_effects(nota, user=user)
            return nota
        except Exception:
            return nota

    def list(self, request):
        queryset = NotaCreditoElectronica.objects.select_related('factura').order_by('-created_at')
        factura_id = request.query_params.get('factura_id')
        if factura_id:
            queryset = queryset.filter(factura_id=factura_id)
        notes = [self._auto_sync_if_needed(nota, user=request.user) for nota in queryset]
        serializer = self.get_serializer(notes, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.select_related('factura').prefetch_related('detalles').filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        nota = self._auto_sync_if_needed(nota, user=request.user)
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
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado creando nota crédito (endpoint legacy) para factura %s', factura.id)
            return Response({'detail': 'Error interno al crear nota crédito.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(_credit_note_api_payload(nota, meta), status=_credit_note_http_status(meta))

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
        filename = f'nota-credito-{nota.number}.pdf'
        if str(request.query_params.get('base64', '')).strip().lower() in {'1', 'true', 'yes'}:
            return Response(
                {
                    'file_name': filename,
                    'pdf_base_64_encoded': base64.b64encode(content).decode('ascii'),
                }
            )
        return _build_file_response(content, filename, 'application/pdf')

    @action(detail=True, methods=['post'], url_path='sincronizar')
    def sincronizar(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            nota, effects = sync_credit_note_with_effects(nota, user=request.user)
            meta = {
                'ok': nota.estado_local in {'ACEPTADA', 'PENDIENTE_DIAN'},
                'result': 'accepted' if nota.estado_local == 'ACEPTADA' else ('pending_dian' if nota.estado_local == 'PENDIENTE_DIAN' else ('rejected' if nota.estado_local == 'RECHAZADA' else ('conflict' if nota.estado_local == 'CONFLICTO_FACTUS' else 'error'))),
                'finalized': nota.estado_local in {'ACEPTADA', 'RECHAZADA'},
                'business_effects_applied': effects,
                'note_id': nota.id,
                'number': nota.number,
                'estado_local': nota.estado_local,
                'estado_electronico': nota.estado_electronico,
                'codigo_error': nota.codigo_error,
                'mensaje_error': nota.mensaje_error,
                'can_sync': nota.estado_local in {'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'},
                'can_retry': nota.estado_local in {'ERROR_INTEGRACION', 'CONFLICTO_FACTUS'},
                'warnings': [],
                'http_status': 202 if nota.estado_local in {'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'} else 200,
            }
        except (CreditNoteValidationError, CreditNoteStateError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Error inesperado sincronizando nota crédito %s', nota.id)
            return Response({'detail': 'Error interno al sincronizar la nota crédito.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(_credit_note_api_payload(nota, meta), status=_credit_note_http_status(meta))

    @action(detail=True, methods=['get'], url_path='estado-remoto')
    def estado_remoto(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        remote = nota.response_json if isinstance(nota.response_json, dict) else {}
        return Response(
            {
                'id': nota.id,
                'estado_local': nota.estado_local,
                'estado_electronico': nota.estado_electronico,
                'reference_code': nota.reference_code,
                'number': nota.number,
                'remote_identifier': nota.remote_identifier,
                'last_sync_at': nota.last_sync_at or nota.synchronized_at,
                'last_remote_error': nota.last_remote_error,
                'sync_metadata': nota.sync_metadata or {},
                'remote_response': remote,
                'detail': 'Estado remoto consultado. Use sincronizar para refrescar conciliación.',
            }
        )

    @action(detail=True, methods=['post'], url_path='reintentar-conciliacion')
    def reintentar_conciliacion(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            nota = sincronizar_nota_credito(nota.id, user=request.user, force_retry=True)
            effects = False
            if nota.estado_local == 'ACEPTADA':
                nota, effects = sync_credit_note_with_effects(nota, user=request.user)
            meta = {
                'ok': nota.estado_local in {'ACEPTADA', 'PENDIENTE_DIAN'},
                'result': 'accepted' if nota.estado_local == 'ACEPTADA' else ('pending_dian' if nota.estado_local == 'PENDIENTE_DIAN' else ('rejected' if nota.estado_local == 'RECHAZADA' else ('conflict' if nota.estado_local == 'CONFLICTO_FACTUS' else 'error'))),
                'finalized': nota.estado_local in {'ACEPTADA', 'RECHAZADA'},
                'business_effects_applied': effects,
                'note_id': nota.id,
                'number': nota.number,
                'estado_local': nota.estado_local,
                'estado_electronico': nota.estado_electronico,
                'codigo_error': nota.codigo_error,
                'mensaje_error': nota.mensaje_error,
                'can_sync': nota.estado_local in {'PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'},
                'can_retry': nota.estado_local in {'ERROR_INTEGRACION', 'CONFLICTO_FACTUS'},
                'warnings': [],
                'http_status': 202 if nota.estado_local in {'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'} else 200,
            }
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(_credit_note_api_payload(nota, meta), status=_credit_note_http_status(meta))

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf_by_id(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not nota.number:
            return Response({'detail': 'La nota crédito aún no tiene número confirmado en Factus/DIAN.'}, status=status.HTTP_409_CONFLICT)
        try:
            from apps.facturacion.services.factus_client import FactusClient

            if nota.pdf_local_path:
                content = read_local_media_file(nota.pdf_local_path)
            else:
                content = FactusClient().download_credit_note_pdf(nota.number)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        filename = f'nota-credito-{nota.number}.pdf'
        if str(request.query_params.get('base64', '')).strip().lower() in {'1', 'true', 'yes'}:
            return Response(
                {
                    'file_name': filename,
                    'pdf_base_64_encoded': base64.b64encode(content).decode('ascii'),
                }
            )
        return _build_file_response(content, filename, 'application/pdf')

    @action(detail=True, methods=['get'], url_path='xml')
    def xml_by_id(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not nota.number:
            return Response({'detail': 'La nota crédito aún no tiene número confirmado en Factus/DIAN.'}, status=status.HTTP_409_CONFLICT)
        try:
            from apps.facturacion.services.factus_client import FactusClient

            if nota.xml_local_path:
                content = read_local_media_file(nota.xml_local_path)
            else:
                content = FactusClient().download_credit_note_xml(nota.number)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        filename = f'nota-credito-{nota.number}.xml'
        if str(request.query_params.get('base64', '')).strip().lower() in {'1', 'true', 'yes'}:
            return Response(
                {
                    'file_name': filename,
                    'xml_base_64_encoded': base64.b64encode(content).decode('ascii'),
                }
            )
        return _build_file_response(content, filename, 'application/xml')

    @action(detail=True, methods=['get'], url_path='correo/contenido')
    def correo_contenido(self, request, pk=None):
        nota = NotaCreditoElectronica.objects.filter(pk=pk).first()
        if nota is None:
            return Response({'detail': 'Nota crédito no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if not nota.number:
            return Response({'detail': 'La nota crédito aún no tiene número confirmado para gestionar correo.'}, status=status.HTTP_409_CONFLICT)
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
        if not nota.number:
            return Response({'detail': 'La nota crédito aún no tiene número confirmado para envío de correo.'}, status=status.HTTP_409_CONFLICT)
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

    def _sync_pending_support_document_from_factus(self) -> DocumentoSoporteElectronico | None:
        try:
            payload = FactusClient().list_support_documents()
        except Exception:
            return None
        data = payload.get('data', payload) if isinstance(payload, dict) else {}
        candidates = []
        if isinstance(data, dict):
            if isinstance(data.get('data'), list):
                candidates = data.get('data') or []
            elif isinstance(data.get('support_documents'), list):
                candidates = data.get('support_documents') or []
            elif isinstance(data.get('support_document'), dict):
                candidates = [data.get('support_document')]
        elif isinstance(data, list):
            candidates = data
        if not candidates:
            return None
        candidate = candidates[0] if isinstance(candidates[0], dict) else None
        if candidate is None:
            return None
        number = str(candidate.get('number') or '').strip()
        if not number:
            return None
        detail_payload = payload
        try:
            detail_payload = FactusClient().get_support_document(number)
        except Exception:
            pass
        detail_data = detail_payload.get('data', detail_payload) if isinstance(detail_payload, dict) else {}
        support_document = detail_data.get('support_document', detail_data) if isinstance(detail_data, dict) else {}
        status_electronic, _status_raw = map_factus_status(detail_payload if isinstance(detail_payload, dict) else payload)
        documento, _created = DocumentoSoporteElectronico.objects.update_or_create(
            number=number,
            defaults={
                'proveedor_nombre': str(
                    support_document.get('supplier', {}).get('names')
                    if isinstance(support_document.get('supplier'), dict)
                    else ''
                ).strip()
                or 'Proveedor pendiente DIAN',
                'proveedor_documento': str(
                    support_document.get('supplier', {}).get('identification')
                    if isinstance(support_document.get('supplier'), dict)
                    else ''
                ).strip(),
                'proveedor_tipo_documento': str(
                    support_document.get('supplier', {}).get('identification_document')
                    if isinstance(support_document.get('supplier'), dict)
                    else ''
                ).strip()
                or 'CC',
                'cufe': str(support_document.get('cufe') or '').strip() or None,
                'uuid': str(support_document.get('uuid') or '').strip() or None,
                'status': status_electronic or 'EN_PROCESO',
                'xml_url': str(support_document.get('xml_url') or '').strip() or None,
                'pdf_url': str(support_document.get('pdf_url') or '').strip() or None,
                'response_json': detail_payload if isinstance(detail_payload, dict) else payload,
            },
        )
        return documento

    def list(self, request):
        queryset = DocumentoSoporteElectronico.objects.order_by('-created_at')
        documents = [self._auto_sync_if_needed(documento) for documento in queryset]
        serializer = self.get_serializer(documents, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        documento = DocumentoSoporteElectronico.objects.filter(pk=pk).first()
        if documento is None:
            return Response({'detail': 'Documento soporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        documento = self._auto_sync_if_needed(documento)
        return Response(DocumentoSoporteListSerializer(documento).data)

    def _auto_sync_if_needed(self, documento: DocumentoSoporteElectronico) -> DocumentoSoporteElectronico:
        if str(documento.status or '').strip().upper() not in {'EN_PROCESO', 'PENDIENTE_DIAN', 'PENDIENTE', 'CONFLICTO_FACTUS'}:
            return documento
        if (timezone.now() - documento.created_at).total_seconds() < 30:
            return documento
        if not documento.number:
            return documento
        try:
            remote = FactusClient().get_support_document(documento.number)
            data = remote.get('data', remote) if isinstance(remote, dict) else {}
            item = data.get('support_document', data) if isinstance(data, dict) else {}
            estado, _estado_raw = map_factus_status(remote)
            documento.status = estado or documento.status
            documento.cufe = str(item.get('cufe') or documento.cufe or '').strip() or documento.cufe
            documento.uuid = str(item.get('uuid') or documento.uuid or '').strip() or documento.uuid
            documento.xml_url = str(item.get('xml_url') or documento.xml_url or '').strip() or documento.xml_url
            documento.pdf_url = str(item.get('pdf_url') or documento.pdf_url or '').strip() or documento.pdf_url
            documento.response_json = remote
            documento.save(update_fields=['status', 'cufe', 'uuid', 'xml_url', 'pdf_url', 'response_json'])
        except Exception:
            return documento
        return documento

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            documento = emitir_documento_soporte(serializer.validated_data, user=request.user)
        except DocumentoSoporteInvalido as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except FactusValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (FactusAPIError, FactusAuthError) as exc:
            if isinstance(exc, FactusAPIError) and int(getattr(exc, 'status_code', 0) or 0) == 409:
                pending_document = self._sync_pending_support_document_from_factus()
                return Response(
                    {
                        'detail': str(exc),
                        'result': 'PENDING_DIAN_CONFLICT',
                        'warning': 'Existe un documento soporte en proceso DIAN en Factus. Sincronice y reintente.',
                        'pending_document': (
                            DocumentoSoporteListSerializer(pending_document).data
                            if pending_document
                            else None
                        ),
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        output = DocumentoSoporteListSerializer(documento)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='sincronizar')
    def sincronizar(self, request, pk=None):
        documento = DocumentoSoporteElectronico.objects.filter(pk=pk).first()
        if documento is None:
            return Response({'detail': 'Documento soporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not documento.number:
            return Response({'detail': 'El documento soporte aún no tiene número confirmado.'}, status=status.HTTP_409_CONFLICT)
        try:
            remote = FactusClient().get_support_document(documento.number)
            data = remote.get('data', remote) if isinstance(remote, dict) else {}
            item = data.get('support_document', data) if isinstance(data, dict) else {}
            estado, _estado_raw = map_factus_status(remote)
            documento.status = estado or documento.status
            documento.cufe = str(item.get('cufe') or documento.cufe or '').strip() or documento.cufe
            documento.uuid = str(item.get('uuid') or documento.uuid or '').strip() or documento.uuid
            documento.xml_url = str(item.get('xml_url') or documento.xml_url or '').strip() or documento.xml_url
            documento.pdf_url = str(item.get('pdf_url') or documento.pdf_url or '').strip() or documento.pdf_url
            documento.response_json = remote
            documento.save(update_fields=['status', 'cufe', 'uuid', 'xml_url', 'pdf_url', 'response_json'])
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(DocumentoSoporteListSerializer(documento).data)

    @action(detail=True, methods=['get'], url_path='estado-remoto')
    def estado_remoto(self, request, pk=None):
        documento = DocumentoSoporteElectronico.objects.filter(pk=pk).first()
        if documento is None:
            return Response({'detail': 'Documento soporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                'id': documento.id,
                'number': documento.number,
                'status': documento.status,
                'cufe': documento.cufe,
                'uuid': documento.uuid,
                'remote_response': documento.response_json or {},
                'detail': 'Estado remoto consultado. Use sincronizar para refrescar datos.',
            }
        )

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

    @action(detail=True, methods=['get'], url_path='xml')
    def xml_by_id(self, request, pk=None):
        documento = DocumentoSoporteElectronico.objects.filter(pk=pk).first()
        if documento is None:
            return Response({'detail': 'Documento soporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not documento.number:
            return Response({'detail': 'El documento soporte aún no tiene número confirmado.'}, status=status.HTTP_409_CONFLICT)
        try:
            content = FactusClient().download_support_document_xml(documento.number)
        except FactusAPIError as exc:
            status_code = int(getattr(exc, 'status_code', 0) or 0)
            if status_code == 409:
                return Response(
                    {'detail': 'El documento soporte aún no ha sido validado por DIAN. Intente sincronizar más tarde.'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({'detail': 'No fue posible descargar el XML del documento soporte.'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        filename = f'documento-soporte-{documento.number}.xml'
        if str(request.query_params.get('base64', '')).strip().lower() in {'1', 'true', 'yes'}:
            return Response(
                {
                    'file_name': filename,
                    'xml_base_64_encoded': base64.b64encode(content).decode('ascii'),
                }
            )
        return _build_file_response(content, filename, 'application/xml')

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf_by_id(self, request, pk=None):
        documento = DocumentoSoporteElectronico.objects.filter(pk=pk).first()
        if documento is None:
            return Response({'detail': 'Documento soporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if not documento.number:
            return Response({'detail': 'El documento soporte aún no tiene número confirmado.'}, status=status.HTTP_409_CONFLICT)
        try:
            content = FactusClient().download_support_document_pdf(documento.number)
        except FactusAPIError as exc:
            status_code = int(getattr(exc, 'status_code', 0) or 0)
            if status_code == 409:
                return Response(
                    {'detail': 'El documento soporte aún no ha sido validado por DIAN. Intente sincronizar más tarde.'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({'detail': 'No fue posible descargar el PDF del documento soporte.'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        filename = f'documento-soporte-{documento.number}.pdf'
        if str(request.query_params.get('base64', '')).strip().lower() in {'1', 'true', 'yes'}:
            return Response(
                {
                    'file_name': filename,
                    'pdf_base_64_encoded': base64.b64encode(content).decode('ascii'),
                }
            )
        return _build_file_response(content, filename, 'application/pdf')

    @action(detail=True, methods=['post'], url_path='eliminar')
    def eliminar(self, request, pk=None):
        documento = DocumentoSoporteElectronico.objects.filter(pk=pk).first()
        if documento is None:
            return Response({'detail': 'Documento soporte no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if str(documento.status or '').strip().upper() in {'ACEPTADA', 'ACEPTADA_CON_OBSERVACIONES'}:
            return Response(
                {'detail': 'No se permite eliminar documentos soporte aceptados fiscalmente.'},
                status=status.HTTP_409_CONFLICT,
            )
        payload = documento.response_json if isinstance(documento.response_json, dict) else {}
        data = payload.get('data', payload) if isinstance(payload, dict) else {}
        support_document = data.get('support_document', data) if isinstance(data, dict) else {}
        reference_code = str(
            support_document.get('reference_code')
            or data.get('reference_code')
            or payload.get('reference_code')
            or documento.number
            or ''
        ).strip()
        if not reference_code:
            return Response({'detail': 'El documento no tiene referencia para eliminar en Factus.'}, status=status.HTTP_409_CONFLICT)
        try:
            provider_response = FactusClient().delete_support_document(reference_code)
        except (FactusValidationError, FactusAPIError, FactusAuthError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        documento.delete()
        return Response({'result': 'deleted', 'reference_code': reference_code, 'provider': provider_response})

    def destroy(self, request, pk=None):
        return self.eliminar(request, pk=pk)
