"""Endpoints de consulta para facturación electrónica."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.facturacion.serializers import FacturaEstadoSerializer
from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services import FacturaNoEncontrada, FactusConsultaError, sync_invoice_status


class FacturaElectronicaViewSet(viewsets.GenericViewSet):
    """ViewSet para consultar y sincronizar estado DIAN de facturas electrónicas."""

    permission_classes = [IsAuthenticated]
    serializer_class = FacturaEstadoSerializer

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
