"""Serializer para payload de impresión POS."""

from rest_framework import serializers

from apps.facturacion.models import FacturaElectronica


class FacturaPOSSerializer(serializers.ModelSerializer):
    numero = serializers.CharField(source='number', read_only=True)
    fecha = serializers.DateTimeField(source='venta.fecha', read_only=True)
    cliente = serializers.CharField(source='venta.cliente.nombre', read_only=True)
    nit_cliente = serializers.CharField(source='venta.cliente.numero_documento', read_only=True)
    items = serializers.SerializerMethodField()
    total = serializers.DecimalField(source='venta.total', max_digits=12, decimal_places=2, read_only=True)
    qr = serializers.ImageField(read_only=True)

    class Meta:
        model = FacturaElectronica
        fields = ['numero', 'fecha', 'cliente', 'nit_cliente', 'items', 'total', 'cufe', 'qr']

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
