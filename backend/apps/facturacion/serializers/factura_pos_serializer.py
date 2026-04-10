"""Serializer para payload de impresión POS."""

from rest_framework import serializers

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.document_print_context import build_document_print_context


class FacturaPOSSerializer(serializers.ModelSerializer):
    numero = serializers.CharField(source='number', read_only=True)
    fecha = serializers.DateTimeField(source='venta.fecha', read_only=True)
    cliente = serializers.CharField(source='venta.cliente.nombre', read_only=True)
    nit_cliente = serializers.CharField(source='venta.cliente.numero_documento', read_only=True)
    items = serializers.SerializerMethodField()
    total = serializers.DecimalField(source='venta.total', max_digits=12, decimal_places=2, read_only=True)
    qr = serializers.ImageField(read_only=True)
    resolucion_numeracion = serializers.SerializerMethodField()
    print_context = serializers.SerializerMethodField()
    documento = serializers.SerializerMethodField()

    class Meta:
        model = FacturaElectronica
        fields = [
            'numero',
            'fecha',
            'cliente',
            'nit_cliente',
            'items',
            'total',
            'cufe',
            'qr',
            'documento',
            'resolucion_numeracion',
            'print_context',
        ]

    def get_items(self, obj: FacturaElectronica):
        return [
            {
                'producto': detalle.producto.nombre,
                'cantidad': detalle.cantidad,
                'precio_unitario': detalle.precio_unitario,
                'total': detalle.total,
            }
            for detalle in obj.venta.detalles.select_related('producto').all()
        ]

    def get_print_context(self, obj: FacturaElectronica):
        return build_document_print_context(obj)

    def get_resolucion_numeracion(self, obj: FacturaElectronica):
        context = self.get_print_context(obj)
        return context.get('resolucion_texto') or 'Documento pendiente de emisión electrónica.'

    def get_documento(self, obj: FacturaElectronica):
        context = self.get_print_context(obj)
        return {
            'tipo': 'FACTURA_ELECTRONICA',
            'numero_real': context.get('numero_documento') or str(obj.number or '').strip(),
            'reference_code': context.get('reference_code') or str(obj.reference_code or '').strip(),
            'estado_emision': context.get('emission_status') or str(obj.estado_electronico or ''),
        }
