from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q, Prefetch
from django.db import transaction
from django.utils import timezone
from datetime import datetime, time
import logging

from apps.facturacion.exceptions import FacturaDuplicadaError
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.serializers import FacturaElectronicaSerializer
from apps.facturacion.services import (
    FactusAPIError,
    FactusAuthError,
    FactusValidationError,
    facturar_venta,
)
from apps.ventas.services import (
    anular_venta,
    build_factura_ready_payload,
    build_pos_ticket_payload,
    cerrar_venta_local,
    enviar_venta_a_caja,
    estado_electronico_ui,
    registrar_salida_inventario,
    validar_para_facturar_en_caja,
)
from apps.ventas.permissions import has_caja_access, is_admin_user

from .models import Cliente, Venta, DetalleVenta, SolicitudDescuento
from .serializers import (
    ClienteSerializer,
    VentaListSerializer,
    VentaDetailSerializer,
    VentaCreateSerializer,
    SolicitudDescuentoSerializer,
)

logger = logging.getLogger(__name__)


def _is_admin(user):
    return is_admin_user(user)


def _is_caja(user):
    return has_caja_access(user)


_registrar_salida_inventario = registrar_salida_inventario


def _to_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'si', 'sí', 'yes', 'y', 'on'}:
            return True
        if normalized in {'false', '0', 'no', 'n', 'off', ''}:
            return False
    return default



class ClienteViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar clientes"""
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo_documento', 'ciudad', 'is_active']
    search_fields = ['numero_documento', 'nombre', 'telefono', 'email']
    ordering_fields = ['nombre', 'created_at']
    ordering = ['nombre']
    
    @action(detail=False, methods=['get'])
    def buscar_por_documento(self, request):
        """
        Busca cliente por número de documento.
        
        GET /api/clientes/buscar_por_documento/?documento=222222
        """
        documento = request.query_params.get('documento', None)
        if not documento:
            return Response(
                {'error': 'Debe proporcionar el parámetro documento'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cliente = Cliente.objects.get(numero_documento=documento, is_active=True)
            serializer = self.get_serializer(cliente)
            return Response(serializer.data)
        except Cliente.DoesNotExist:
            return Response(
                {'error': 'Cliente no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class VentaViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar ventas"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo_comprobante', 'estado', 'vendedor', 'cliente']
    search_fields = ['numero_comprobante', 'cliente__nombre', 'cliente__numero_documento']
    ordering_fields = ['fecha', 'total']
    ordering = ['-fecha']

    @staticmethod
    def _get_fecha_range(fecha_inicio, fecha_fin):
        tz = timezone.get_current_timezone()
        inicio_dt = fin_dt = None
        if fecha_inicio:
            inicio_date = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            inicio_dt = timezone.make_aware(
                datetime.combine(inicio_date, time.min),
                tz
            )
        if fecha_fin:
            fin_date = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            fin_dt = timezone.make_aware(
                datetime.combine(fin_date, time.max),
                tz
            )
        return inicio_dt, fin_dt

    def get_queryset(self):
        detalles_queryset = DetalleVenta.objects.select_related(
            # Evita N+1 al serializar cada detalle de venta.
            'producto',
            # Pre-carga relaciones frecuentes del producto en reportes/listados.
            'producto__categoria',
            'producto__proveedor',
        )
        queryset = Venta.objects.select_related(
            'cliente', 'vendedor', 'factura_electronica_factus'
        ).prefetch_related(
            Prefetch('detalles', queryset=detalles_queryset)
        ).all()
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        estado = self.request.query_params.get('estado')
        inicio_dt, fin_dt = self._get_fecha_range(fecha_inicio, fecha_fin)
        date_field = 'facturada_at' if estado in {'FACTURADA', 'COBRADA'} else 'fecha'
        if inicio_dt:
            queryset = queryset.filter(**{f'{date_field}__gte': inicio_dt})
        if fin_dt:
            queryset = queryset.filter(**{f'{date_field}__lte': fin_dt})
        return queryset
    
    def get_serializer_class(self):
        """Retorna el serializer apropiado según la acción"""
        if self.action == 'list':
            return VentaListSerializer
        elif self.action in {'create', 'update', 'partial_update'}:
            return VentaCreateSerializer
        return VentaDetailSerializer

    def perform_create(self, serializer):
        user = self.request.user
        vendedor = serializer.validated_data.get('vendedor')
        if not _is_admin(user):
            vendedor = user
        tipo_comprobante = serializer.validated_data.get('tipo_comprobante')
        estado = 'BORRADOR' if tipo_comprobante == 'FACTURA' else 'COBRADA'
        serializer.save(
            vendedor=vendedor or user,
            creada_por=user,
            estado=estado,
        )

    def create(self, request, *args, **kwargs):
        payload = request.data.copy()
        facturar_directo = bool(payload.pop('facturar_directo', False))
        logger.info(
            'ventas.create.payload user_id=%s facturar_directo=%s payload=%s',
            getattr(request.user, 'id', None),
            facturar_directo,
            payload,
        )
        serializer = self.get_serializer(data=payload)
        if not serializer.is_valid():
            logger.warning(
                'ventas.create.validation_error user_id=%s errors=%s payload=%s',
                getattr(request.user, 'id', None),
                serializer.errors,
                payload,
            )
            raise ValidationError(serializer.errors)
        with transaction.atomic():
            self.perform_create(serializer)
            venta = serializer.instance
            if facturar_directo and venta.tipo_comprobante == 'FACTURA':
                logger.info('ventas.create.cerrar_venta_local venta_id=%s user_id=%s', venta.id, getattr(request.user, 'id', None))
                cerrar_venta_local(venta, request.user)
        detail_serializer = VentaDetailSerializer(venta, context=self.get_serializer_context())
        headers = self.get_success_headers(detail_serializer.data)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _puede_editar_venta(self, user, venta):
        """Verifica si el usuario puede editar la venta según su estado."""
        if _is_admin(user):
            return True
        if venta.estado == 'BORRADOR':
            return True
        # Cajeros pueden editar ventas enviadas a caja (para actualizar pago)
        if venta.estado == 'ENVIADA_A_CAJA' and _is_caja(user):
            return True
        return False

    def update(self, request, *args, **kwargs):
        venta = self.get_object()
        if not self._puede_editar_venta(request.user, venta):
            return Response(
                {'error': 'Solo se pueden editar ventas en borrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        venta = self.get_object()
        if not self._puede_editar_venta(request.user, venta):
            return Response(
                {'error': 'Solo se pueden editar ventas en borrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def remisiones_pendientes(self, request):
        """
        Retorna remisiones que aún no se han convertido en facturas.
        Útil para el reporte de "Remisiones por facturar".
        """
        remisiones = self.get_queryset().filter(
            tipo_comprobante='REMISION',
            estado='COBRADA',
            facturas_generadas__isnull=True  # No tiene factura asociada
        )
        
        serializer = VentaListSerializer(remisiones, many=True)
        return Response(serializer.data)


    @action(detail=True, methods=['post'])
    def convertir_a_factura(self, request, pk=None):
        """
        Convierte una remisión en factura electrónica.
        
        POST /api/ventas/{id}/convertir_a_factura/
        """
        remision = self.get_object()
        
        if remision.tipo_comprobante != 'REMISION':
            return Response(
                {'error': 'Solo se pueden convertir remisiones a facturas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if remision.estado != 'COBRADA':
            return Response(
                {'error': 'Solo se pueden facturar remisiones confirmadas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            factura = remision.convertir_a_factura()
            factura.estado = 'COBRADA'
            factura.facturada_por = request.user
            factura.facturada_at = timezone.now()
            factura.save()
            serializer = VentaDetailSerializer(factura)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def anular(self, request, pk=None):
        """
        Anula una venta.
        
        POST /api/ventas/{id}/anular/
        Body: {
            "motivo": "DEVOLUCION_TOTAL",
            "descripcion": "Cliente devolvió la mercancía",
            "devuelve_inventario": true
        }
        """
        motivo = request.data.get('motivo')
        descripcion = request.data.get('descripcion', '')
        devuelve_inventario = _to_bool(request.data.get('devuelve_inventario'), default=True)
        
        if not motivo:
            return Response(
                {'error': 'Debe proporcionar el motivo de anulación'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            venta = (
                Venta.objects.select_for_update()
                .select_related('factura_electronica_factus')
                .prefetch_related('detalles', 'detalles__producto')
                .get(pk=pk)
            )
            try:
                nota_credito = anular_venta(
                    venta,
                    request.user,
                    motivo=motivo,
                    descripcion=descripcion,
                    devuelve_inventario=devuelve_inventario,
                )
            except ValidationError as error:
                return Response({'error': error.detail}, status=status.HTTP_400_BAD_REQUEST)
            except (FactusAPIError, FactusAuthError, FactusValidationError) as exc:
                logger.exception(
                    'No se anuló venta_id=%s porque falló emisión de nota crédito en Factus',
                    venta.id,
                )
                return Response(
                    {
                        'error': 'No fue posible emitir la nota crédito electrónica en Factus.',
                        'detail': str(exc),
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        serializer = VentaDetailSerializer(venta)
        data = serializer.data
        if nota_credito is not None:
            data['nota_credito_emitida'] = {
                'id': nota_credito.id,
                'number': nota_credito.number,
                'status': nota_credito.status,
            }
        return Response(data)

    @action(detail=True, methods=['post'], url_path='enviar-a-caja')
    def enviar_a_caja(self, request, pk=None):
        with transaction.atomic():
            venta = (
                Venta.objects.select_for_update()
                .select_related('cliente', 'vendedor')
                .prefetch_related('detalles', 'detalles__producto')
                .get(pk=pk)
            )

            try:
                enviar_venta_a_caja(venta, request.user)
            except ValidationError as error:
                return Response({'error': error.detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VentaDetailSerializer(venta)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def facturar(self, request, pk=None):
        """Cierra/cobra venta local e intenta emitir factura electrónica en Factus."""
        logger.info(
            'ventas.facturar.inicio venta_id=%s user_id=%s ruta=/api/ventas/%s/facturar/',
            pk,
            getattr(request.user, 'id', None),
            pk,
        )
        venta = self.get_object()

        try:
            with transaction.atomic():
                venta = (
                    Venta.objects.select_for_update()
                    .select_related('cliente', 'vendedor')
                    .prefetch_related('detalles', 'detalles__producto')
                    .get(pk=pk)
                )
                if venta.tipo_comprobante != 'FACTURA':
                    raise ValidationError('Solo se puede facturar electrónicamente comprobantes de tipo FACTURA.')
                if venta.estado == 'ANULADA':
                    raise ValidationError('No se puede facturar una venta anulada.')
                if venta.estado not in {'COBRADA', 'FACTURADA'}:
                    cerrar_venta_local(venta, request.user)

            logger.info('ventas.facturar.enviando_factus venta_id=%s', venta.id)
            factura = facturar_venta(venta.id, triggered_by=request.user)
            logger.info('ventas.facturar.factus_ok venta_id=%s factura_number=%s status=%s', venta.id, factura.number, factura.status)
            venta.refresh_from_db()
        except ValidationError as exc:
            logger.warning('ventas.facturar.validation_error venta_id=%s error=%s', pk, exc.detail)
            return Response({'error': exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        except (FactusValidationError, FactusAuthError, FactusAPIError, FacturaDuplicadaError) as exc:
            logger.exception('ventas.facturar.factus_error venta_id=%s', pk)
            venta.refresh_from_db()
            factura_error = FacturaElectronica.objects.filter(venta=venta).first()
            return Response(
                {
                    'ok': False,
                    'message': str(exc),
                    'warning': 'FACTURA_LOCAL_OK_EMISION_ELECTRONICA_FALLIDA',
                    'venta_id': venta.id,
                    'venta': VentaDetailSerializer(venta).data,
                    'factura_electronica': (
                        FacturaElectronicaSerializer(factura_error).data
                        if factura_error
                        else None
                    ),
                    'numero_factura': factura_error.number if factura_error else None,
                    'estado_local': venta.estado,
                    'estado_venta': venta.estado,
                    'estado_electronico': estado_electronico_ui(factura_error) if factura_error else 'ERROR',
                    'status': factura_error.status if factura_error else 'ERROR',
                    'cufe': factura_error.cufe if factura_error else '',
                    'uuid': factura_error.uuid if factura_error else '',
                    'reference_code': factura_error.reference_code if factura_error else '',
                    'pos_ticket': build_pos_ticket_payload(venta, factura_error) if factura_error else None,
                    'factus_sent': False,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception('ventas.facturar.error_no_controlado venta_id=%s', venta.id)
            venta.refresh_from_db()
            factura_error = FacturaElectronica.objects.filter(venta=venta).first()
            return Response(
                {
                    'ok': False,
                    'message': f'Error interno al facturar: {exc}',
                    'venta_id': venta.id,
                    'numero_factura': None,
                    'estado_local': venta.estado,
                    'estado_venta': venta.estado,
                    'estado_electronico': estado_electronico_ui(factura_error) if factura_error else 'ERROR',
                    'status': 'ERROR',
                    'factus_sent': False,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        data = {
            'ok': True,
            'message': 'Factura electrónica generada correctamente',
            'venta_id': venta.id,
            'venta': VentaDetailSerializer(venta).data,
            'factura_electronica': FacturaElectronicaSerializer(factura).data,
            'factura_lista': build_factura_ready_payload(venta, factura),
            'numero_factura': factura.number,
            'estado_local': venta.estado,
            'estado_venta': venta.estado,
            'estado_electronico': estado_electronico_ui(factura),
            'status': factura.status,
            'cufe': factura.cufe,
            'uuid': factura.uuid,
            'reference_code': factura.reference_code,
            'pos_ticket': build_pos_ticket_payload(venta, factura),
            'factus_sent': True,
            'pdf_url': factura.pdf_url,
            'xml_url': factura.xml_url,
        }
        return Response(data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """
        Retorna estadísticas de ventas.
        
        GET /api/ventas/estadisticas/?fecha_inicio=2025-01-01&fecha_fin=2025-01-31
        """
        fecha_inicio = request.query_params.get('fecha_inicio')
        fecha_fin = request.query_params.get('fecha_fin')
        
        ventas = self.get_queryset().filter(estado='COBRADA')
        
        inicio_dt, fin_dt = self._get_fecha_range(fecha_inicio, fecha_fin)
        if inicio_dt:
            ventas = ventas.filter(fecha__gte=inicio_dt)
        if fin_dt:
            ventas = ventas.filter(fecha__lte=fin_dt)
        
        stats = ventas.aggregate(
            total_ventas=Count('id'),
            total_facturado=Sum('total'),
            total_cotizaciones=Count('id', filter=Q(tipo_comprobante='COTIZACION')),
            total_remisiones=Count('id', filter=Q(tipo_comprobante='REMISION')),
            total_facturas=Count('id', filter=Q(tipo_comprobante='FACTURA')),
            total_facturas_valor=Sum('total', filter=Q(tipo_comprobante='FACTURA')),
            total_remisiones_valor=Sum('total', filter=Q(tipo_comprobante='REMISION')),
        )

        ventas_por_usuario = (
            ventas.values(
                'vendedor_id',
                'vendedor__first_name',
                'vendedor__last_name',
                'vendedor__username',
            )
            .annotate(
                total_facturas=Count('id', filter=Q(tipo_comprobante='FACTURA')),
                total_remisiones=Count('id', filter=Q(tipo_comprobante='REMISION')),
            )
            .order_by('vendedor__first_name', 'vendedor__last_name', 'vendedor__username')
        )

        facturas_por_usuario = []
        remisiones_por_usuario = []
        for item in ventas_por_usuario:
            nombre = f"{item['vendedor__first_name']} {item['vendedor__last_name']}".strip()
            if not nombre:
                nombre = item['vendedor__username']
            if item['total_facturas'] > 0:
                facturas_por_usuario.append(
                    {'usuario': nombre, 'cuentas': item['total_facturas']}
                )
            if item['total_remisiones'] > 0:
                remisiones_por_usuario.append(
                    {'usuario': nombre, 'cuentas': item['total_remisiones']}
                )

        stats['facturas_por_usuario'] = facturas_por_usuario
        stats['remisiones_por_usuario'] = remisiones_por_usuario
        
        return Response(stats)


class CajaViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = VentaDetailSerializer

    def get_queryset(self):
        detalles_queryset = DetalleVenta.objects.select_related(
            # Evita consultas por cada detalle y su producto.
            'producto',
            # Pre-carga datos asociados usados en listados/reportes de caja.
            'producto__categoria',
            'producto__proveedor',
        )
        return Venta.objects.select_related(
            'cliente',
            'vendedor',
            'facturada_por',
            'enviada_a_caja_por',
            'factura_electronica_factus',
        ).prefetch_related(
            Prefetch('detalles', queryset=detalles_queryset)
        )

    def _require_caja(self, request):
        if not _is_caja(request.user):
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _validar_para_facturar(self, venta):
        validar_para_facturar_en_caja(venta)

    @action(detail=False, methods=['get'], url_path='pendientes')
    def pendientes(self, request):
        permission_response = self._require_caja(request)
        if permission_response:
            return permission_response

        ventas = self.get_queryset().filter(
            tipo_comprobante='FACTURA',
            estado='ENVIADA_A_CAJA',
            enviada_a_caja_at__isnull=False,
            facturada_at__isnull=True,
            facturada_por__isnull=True,
        )

        fecha = request.query_params.get('fecha')
        if fecha:
            try:
                fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Formato de fecha inválido. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            ventas = ventas.filter(enviada_a_caja_at__date=fecha_dt)

        ventas = ventas.order_by(
            'enviada_a_caja_at',
            'id',
        )
        serializer = VentaListSerializer(ventas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='detalle')
    def detalle(self, request, pk=None):
        permission_response = self._require_caja(request)
        if permission_response:
            return permission_response

        venta = self.get_object()
        if venta.tipo_comprobante != 'FACTURA' or venta.estado != 'ENVIADA_A_CAJA':
            return Response(
                {'error': 'La venta no está disponible para cargarse en caja.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = VentaDetailSerializer(venta)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def facturar(self, request, pk=None):
        logger.info(
            'caja.facturar.inicio venta_id=%s user_id=%s username=%s ruta=/api/caja/%s/facturar/',
            pk,
            getattr(request.user, 'id', None),
            getattr(request.user, 'username', None),
            pk,
        )
        permission_response = self._require_caja(request)
        if permission_response:
            logger.warning('caja.facturar.no_autorizado venta_id=%s user_id=%s', pk, getattr(request.user, 'id', None))
            return permission_response

        try:
            with transaction.atomic():
                venta = (
                    Venta.objects.select_for_update()
                    .select_related('cliente', 'vendedor')
                    .prefetch_related('detalles', 'detalles__producto')
                    .get(pk=pk)
                )
                logger.info('caja.facturar.validando venta_id=%s estado=%s tipo=%s', venta.id, venta.estado, venta.tipo_comprobante)
                self._validar_para_facturar(venta)
                logger.info('caja.facturar.validacion_ok venta_id=%s', venta.id)
                cerrar_venta_local(venta, request.user)
                logger.info('caja.facturar.estado_local_ok venta_id=%s estado=%s', venta.id, venta.estado)

            logger.info('caja.facturar.enviando_factus venta_id=%s', venta.id)
            factura = facturar_venta(venta.id, triggered_by=request.user)
            venta.refresh_from_db()
            logger.info(
                'caja.facturar.factus_ok venta_id=%s numero=%s status=%s cufe=%s',
                venta.id,
                factura.number,
                factura.status,
                factura.cufe,
            )
        except ValidationError as error:
            logger.warning('caja.facturar.validacion_error venta_id=%s error=%s', pk, error.detail)
            return Response({'error': error.detail}, status=status.HTTP_400_BAD_REQUEST)
        except FacturaDuplicadaError as error:
            factura = FacturaElectronica.objects.filter(venta_id=pk).first()
            if factura is None:
                logger.error('caja.facturar.duplicada_sin_registro venta_id=%s error=%s', pk, str(error))
                return Response({'error': str(error)}, status=status.HTTP_409_CONFLICT)
            logger.warning('caja.facturar.duplicada_reutilizada venta_id=%s factura=%s', pk, factura.number)
        except (FactusValidationError, FactusAuthError, FactusAPIError) as error:
            logger.exception('caja.facturar.factus_error venta_id=%s', pk)
            if 'venta' in locals():
                venta.refresh_from_db()
            factura_error = FacturaElectronica.objects.filter(venta_id=pk).first()
            return Response(
                {
                    'ok': False,
                    'message': str(error),
                    'venta_id': int(pk) if pk else None,
                    'numero_factura': None,
                    'estado_local': venta.estado if 'venta' in locals() else 'COBRADA',
                    'estado_venta': venta.estado if 'venta' in locals() else 'COBRADA',
                    'estado_electronico': estado_electronico_ui(factura_error) if factura_error else 'ERROR',
                    'cufe': '',
                    'uuid': '',
                    'reference_code': '',
                    'pos_ticket': None,
                    'factus_sent': False,
                    'status': 'ERROR',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as error:
            logger.exception('caja.facturar.error_no_controlado venta_id=%s', pk)
            if 'venta' in locals():
                venta.refresh_from_db()
            factura_error = FacturaElectronica.objects.filter(venta_id=pk).first()
            return Response(
                {
                    'ok': False,
                    'message': f'Error interno al facturar: {error}',
                    'venta_id': int(pk) if pk else None,
                    'numero_factura': None,
                    'estado_local': venta.estado if 'venta' in locals() else 'COBRADA',
                    'estado_venta': venta.estado if 'venta' in locals() else 'COBRADA',
                    'estado_electronico': estado_electronico_ui(factura_error) if factura_error else 'ERROR',
                    'status': 'ERROR',
                    'factus_sent': False,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = VentaDetailSerializer(venta)
        logger.info(
            'caja.facturar.fin_ok venta_id=%s numero=%s estado_local=%s estado_electronico=%s',
            venta.id,
            factura.number,
            venta.estado,
            factura.status,
        )
        return Response(
            {
                'ok': True,
                'message': 'Factura electrónica emitida correctamente en Factus.',
                'venta_id': venta.id,
                'venta': serializer.data,
                'factura_electronica': FacturaElectronicaSerializer(factura).data,
                'factura_lista': build_factura_ready_payload(venta, factura),
                'numero_factura': factura.number,
                'estado_local': venta.estado,
                'estado_venta': venta.estado,
                'estado_electronico': estado_electronico_ui(factura),
                'status': factura.status,
                'cufe': factura.cufe,
                'uuid': factura.uuid,
                'reference_code': factura.reference_code,
                'send_email': bool(factura.response_json.get('request', {}).get('send_email', False)),
                'pos_ticket': build_pos_ticket_payload(venta, factura),
                'factus_sent': True,
                'errores': [],
            }
        )


class SolicitudDescuentoViewSet(viewsets.ModelViewSet):
    """ViewSet para solicitudes de descuento"""
    serializer_class = SolicitudDescuentoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'vendedor', 'aprobador']
    search_fields = ['vendedor__username', 'aprobador__username']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        base_queryset = SolicitudDescuento.objects.select_related('vendedor', 'aprobador')
        if user.is_superuser or user.is_staff or getattr(user, 'tipo_usuario', None) == 'ADMIN':
            return base_queryset.filter(aprobador=user)
        return base_queryset.filter(vendedor=user)

    def perform_create(self, serializer):
        aprobador = serializer.validated_data.get('aprobador')
        if not aprobador or not (
            aprobador.is_superuser
            or aprobador.is_staff
            or getattr(aprobador, 'tipo_usuario', None) == 'ADMIN'
        ):
            raise ValidationError({'aprobador': 'Aprobador inválido.'})
        serializer.save(vendedor=self.request.user)

    def update(self, request, *args, **kwargs):
        if request.user != self.get_object().aprobador:
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if request.user != self.get_object().aprobador:
            return Response({'detail': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)
