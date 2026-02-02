from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from apps.inventario.models import Categoria, Producto, Proveedor
from apps.usuarios.models import Usuario
from apps.ventas.models import Cliente, Venta, DetalleVenta


class CajaVentaFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vendedor = Usuario.objects.create_user(
            username='vendedor',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.cajero = Usuario.objects.create_user(
            username='cajero',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.cajero.es_cajero = True
        self.cajero.save(update_fields=['es_cajero'])

        self.categoria = Categoria.objects.create(nombre='General')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor')
        self.producto = Producto.objects.create(
            codigo='P-001',
            nombre='Producto prueba',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('100'),
            precio_venta=Decimal('200'),
            precio_venta_minimo=Decimal('150'),
            stock=10,
            stock_minimo=1,
            iva_porcentaje=Decimal('19'),
        )
        self.cliente = Cliente.objects.create(
            tipo_documento='CC',
            numero_documento='123456',
            nombre='Cliente prueba',
        )

    def _crear_payload(self):
        return {
            'tipo_comprobante': 'FACTURA',
            'cliente': self.cliente.id,
            'vendedor': self.vendedor.id,
            'subtotal': '200.00',
            'descuento_porcentaje': '0',
            'descuento_valor': '0',
            'iva': '38.00',
            'total': '238.00',
            'medio_pago': 'EFECTIVO',
            'efectivo_recibido': '238.00',
            'cambio': '0',
            'detalles': [
                {
                    'producto': self.producto.id,
                    'cantidad': 1,
                    'precio_unitario': '200.00',
                    'descuento_unitario': '0',
                    'iva_porcentaje': '19',
                    'subtotal': '200.00',
                    'total': '238.00',
                }
            ],
        }

    def test_vendedor_no_puede_facturar(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.vendedor,
            subtotal=Decimal('200'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('38'),
            total=Decimal('238'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('238'),
            cambio=Decimal('0'),
            estado='ENVIADA_A_CAJA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )

        self.client.force_authenticate(user=self.vendedor)
        response = self.client.post(f'/api/caja/{venta.id}/facturar/')
        self.assertEqual(response.status_code, 403)

    def test_caja_puede_facturar(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.vendedor,
            subtotal=Decimal('200'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('38'),
            total=Decimal('238'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('238'),
            cambio=Decimal('0'),
            estado='ENVIADA_A_CAJA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(f'/api/caja/{venta.id}/facturar/')
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')
        self.assertIsNotNone(venta.numero_comprobante)

    def test_estados_cambian_correctamente(self):
        self.client.force_authenticate(user=self.vendedor)
        response = self.client.post('/api/ventas/', self._crear_payload(), format='json')
        self.assertEqual(response.status_code, 201)
        venta_id = response.data['id']
        venta = Venta.objects.get(id=venta_id)
        self.assertEqual(venta.estado, 'BORRADOR')

        response = self.client.post(f'/api/ventas/{venta_id}/enviar-a-caja/')
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'ENVIADA_A_CAJA')

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(f'/api/caja/{venta_id}/facturar/')
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')
