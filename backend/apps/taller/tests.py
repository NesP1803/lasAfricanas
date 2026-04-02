from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.inventario.models import Categoria, MovimientoInventario, Producto, Proveedor
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


class OrdenTallerAgregarRepuestoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.usuario = Usuario.objects.create_user(
            username='tecnico_stock',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.client.force_authenticate(user=self.usuario)

        self.categoria = Categoria.objects.create(nombre='General')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor')
        self.producto = Producto.objects.create(
            codigo='REP-NEG-001',
            nombre='Repuesto con stock limitado',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('3000.00'),
            precio_venta_minimo=Decimal('2500.00'),
            stock=Decimal('0.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=False,
        )
        self.cliente = Cliente.objects.create(
            tipo_documento='CC',
            numero_documento='998877',
            nombre='Cliente Taller',
        )
        self.mecanico = Mecanico.objects.create(nombre='Mecánico 1')
        self.moto = Moto.objects.create(
            placa='XYZ987',
            marca='Yamaha',
            cliente=self.cliente,
            mecanico=self.mecanico,
            proveedor=self.proveedor,
        )
        self.orden = OrdenTaller.objects.create(moto=self.moto, mecanico=self.mecanico)

    def test_agregar_repuesto_permite_stock_negativo(self):
        response = self.client.post(
            f'/api/ordenes-taller/{self.orden.id}/agregar_repuesto/',
            {'producto': self.producto.id, 'cantidad': '2'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['mensaje'], 'Repuesto agregado correctamente')
        self.assertEqual(Decimal(response.data['stock_anterior']), Decimal('0.00'))
        self.assertEqual(Decimal(response.data['stock_actual']), Decimal('-2.00'))
        self.assertTrue(response.data['stock_negativo'])

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, Decimal('-2.00'))

        movimiento = MovimientoInventario.objects.get(producto=self.producto)
        self.assertEqual(movimiento.stock_anterior, Decimal('0.00'))
        self.assertEqual(movimiento.stock_nuevo, Decimal('-2.00'))
        self.assertEqual(movimiento.cantidad, Decimal('-2.00'))

    def test_agregar_repuesto_rechaza_cantidad_no_positiva(self):
        response = self.client.post(
            f'/api/ordenes-taller/{self.orden.id}/agregar_repuesto/',
            {'producto': self.producto.id, 'cantidad': '0'},
            format='json',
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['error'], 'Cantidad inválida')
