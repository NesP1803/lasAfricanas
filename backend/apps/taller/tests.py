from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.inventario.models import Categoria, Producto, Proveedor
from apps.taller.models import Mecanico, Moto, OrdenRepuesto, OrdenTaller
from apps.usuarios.models import Usuario
from apps.ventas.models import Cliente
from apps.ventas.services.cerrar_venta import validar_detalles_venta


class OrdenTallerFacturacionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vendedor = Usuario.objects.create_user(
            username='tecnico',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.client.force_authenticate(user=self.vendedor)

        self.categoria = Categoria.objects.create(nombre='General')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor')

        self.producto_gravado = Producto.objects.create(
            codigo='REP-IVA-001',
            nombre='Repuesto gravado',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('3000.00'),
            precio_venta_minimo=Decimal('2500.00'),
            stock=Decimal('20.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=False,
        )
        self.producto_exento = Producto.objects.create(
            codigo='REP-EX-001',
            nombre='Repuesto exento',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('1200.00'),
            precio_venta_minimo=Decimal('1000.00'),
            stock=Decimal('20.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=True,
        )

    def _crear_orden(self):
        cliente = Cliente.objects.create(
            tipo_documento='CC',
            numero_documento='123123',
            nombre='Cliente Taller',
        )
        mecanico = Mecanico.objects.create(nombre='Mecánico 1')
        moto = Moto.objects.create(
            placa='ABC123',
            marca='Honda',
            cliente=cliente,
            mecanico=mecanico,
            proveedor=self.proveedor,
        )
        return OrdenTaller.objects.create(moto=moto, mecanico=mecanico)

    def test_facturar_orden_taller_usa_semantica_iva_incluido(self):
        orden = self._crear_orden()
        OrdenRepuesto.objects.create(
            orden=orden,
            producto=self.producto_gravado,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('3000.00'),
        )

        response = self.client.post(f'/api/ordenes-taller/{orden.id}/facturar/', {'tipo_comprobante': 'FACTURA'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        orden.refresh_from_db()
        venta = orden.venta
        detalle = venta.detalles.get()

        self.assertEqual(detalle.total, Decimal('3000.00'))
        self.assertEqual(detalle.subtotal, Decimal('2521.01'))
        self.assertEqual(venta.subtotal, Decimal('2521.01'))
        self.assertEqual(venta.iva, Decimal('478.99'))
        self.assertEqual(venta.total, Decimal('3000.00'))
        self.assertEqual(venta.subtotal + venta.iva - venta.descuento_valor, venta.total)
        self.assertEqual(validar_detalles_venta(venta)[0].id, detalle.id)

    def test_facturar_orden_taller_respeta_items_exentos(self):
        orden = self._crear_orden()
        OrdenRepuesto.objects.create(
            orden=orden,
            producto=self.producto_exento,
            cantidad=Decimal('2.00'),
            precio_unitario=Decimal('1200.00'),
        )

        response = self.client.post(f'/api/ordenes-taller/{orden.id}/facturar/', {'tipo_comprobante': 'FACTURA'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        orden.refresh_from_db()
        venta = orden.venta
        detalle = venta.detalles.get()

        self.assertEqual(detalle.total, Decimal('2400.00'))
        self.assertEqual(detalle.subtotal, Decimal('2400.00'))
        self.assertEqual(venta.subtotal, Decimal('2400.00'))
        self.assertEqual(venta.iva, Decimal('0.00'))
        self.assertEqual(venta.total, Decimal('2400.00'))
        self.assertEqual(venta.subtotal + venta.iva - venta.descuento_valor, venta.total)
