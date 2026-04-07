from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.db import DataError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventario.models import Categoria, Producto, Proveedor, MovimientoInventario
from apps.usuarios.models import Usuario
from apps.facturacion.models import FacturaElectronica
from apps.ventas.models import Cliente, Venta, DetalleVenta
from apps.ventas.views import _factus_http_status_and_code, _registrar_salida_inventario
from apps.ventas.services.cerrar_venta import build_pos_ticket_payload, cerrar_venta_local
from apps.ventas.services.enviar_venta_a_caja import enviar_venta_a_caja


class FactusErrorMappingTests(TestCase):
    def test_numbering_range_id_invalido_retorna_422_local(self):
        from apps.facturacion.services import FactusAPIError

        exc = FactusAPIError(
            'Factus rechazó la factura',
            status_code=422,
            provider_payload={
                'data': {
                    'errors': {
                        'numbering_range_id': ['El campo id rango de numeración es inválido.'],
                    }
                }
            },
        )
        http_status, error_code = _factus_http_status_and_code(exc)
        self.assertEqual(http_status, 422)
        self.assertEqual(error_code, 'ERROR_RANGO_INVALIDO')


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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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


    def test_facturar_venta_marca_inventario_ya_afectado(self):
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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
        self.assertTrue(venta.inventario_ya_afectado)

    def test_reintento_registro_salida_no_duplica_movimientos(self):
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
        )
        detalle = DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )

        _registrar_salida_inventario(venta, self.cajero, detalles=[detalle])
        venta.refresh_from_db()
        self.assertTrue(venta.inventario_ya_afectado)
        self.assertEqual(MovimientoInventario.objects.filter(tipo='SALIDA').count(), 1)

        _registrar_salida_inventario(venta, self.cajero, detalles=[detalle])
        self.assertEqual(MovimientoInventario.objects.filter(tipo='SALIDA').count(), 1)

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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')
        self.assertEqual(self.producto.stock, Decimal('9'))
        self.assertTrue(response.data.get('factus_sent'))

    def test_anular_venta_facturada_restituye_stock_real(self):
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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
        facturar_response = self.client.post(f'/api/caja/{venta.id}/facturar/')
        self.assertEqual(facturar_response.status_code, 200)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, Decimal('9'))

        self.client.force_authenticate(user=self.vendedor)
        anular_response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {
                'motivo': 'DEVOLUCION_TOTAL',
                'descripcion': 'Anulación prueba',
                'devuelve_inventario': True,
            },
            format='json',
        )
        self.assertEqual(anular_response.status_code, 200)

        venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'ANULADA')
        self.assertEqual(self.producto.stock, Decimal('10'))

    @patch('apps.ventas.services.anular_venta.create_credit_note')
    def test_anular_factura_electronica_aceptada_exige_nota_credito(self, mocked_create_credit_note):
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
            estado='FACTURADA',
            inventario_ya_afectado=True,
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
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
        FacturaElectronica.objects.create(
            venta=venta,
            cufe='CUFE-001',
            uuid='UUID-001',
            number='SETP-100',
            reference_code='SETP-100',
            status='ACEPTADA',
            xml_url='https://example.com/invoice.xml',
            pdf_url='https://example.com/invoice.pdf',
            response_json={},
        )
        mocked_create_credit_note.return_value = (MagicMock(id=10, number='NC-001', estado_local='ACEPTADA'), {'result': 'accepted', 'ok': True, 'finalized': True, 'business_effects_applied': True})

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {'motivo': 'DEVOLUCION_TOTAL', 'descripcion': 'test'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        mocked_create_credit_note.assert_called_once()
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'ANULADA')


class VentaServicesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = Usuario.objects.create_user(username='svc-user', password='pass1234')
        self.vendedor = self.user
        self.cajero = Usuario.objects.create_user(username='svc-cajero', password='pass1234')
        self.cajero.es_cajero = True
        self.cajero.save(update_fields=['es_cajero'])
        self.cliente = Cliente.objects.create(
            tipo_documento='CC',
            numero_documento='998877',
            nombre='Cliente servicio',
        )
        self.categoria = Categoria.objects.create(nombre='Svc categoria')
        self.proveedor = Proveedor.objects.create(nombre='Svc proveedor')
        self.producto = Producto.objects.create(
            codigo='P-SVC',
            nombre='Producto servicio',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('10'),
            precio_venta=Decimal('20'),
            precio_venta_minimo=Decimal('15'),
            stock=10,
            stock_minimo=1,
            iva_porcentaje=Decimal('19'),
        )

    def _crear_venta_borrador(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('20'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('3.8'),
            total=Decimal('23.8'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('23.8'),
            cambio=Decimal('0'),
            estado='BORRADOR',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('20'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('20'),
            total=Decimal('23.8'),
        )
        return venta

    def test_enviar_venta_a_caja_service(self):
        venta = self._crear_venta_borrador()
        enviar_venta_a_caja(venta, self.user)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'ENVIADA_A_CAJA')
        self.assertEqual(venta.enviada_a_caja_por_id, self.user.id)
        self.assertIsNotNone(venta.enviada_a_caja_at)

    def test_cerrar_venta_local_service_afecta_inventario(self):
        venta = self._crear_venta_borrador()
        cerrar_venta_local(venta, self.user)
        venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'COBRADA')
        self.assertTrue(venta.inventario_ya_afectado)
        self.assertEqual(self.producto.stock, Decimal('9'))

    @patch('apps.ventas.services.anular_venta.create_credit_note')
    def test_anular_factura_electronica_si_factus_falla_no_anula_ni_restituye_stock(self, mocked_create_credit_note):
        from apps.facturacion.services import FactusAPIError

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
            estado='FACTURADA',
            inventario_ya_afectado=True,
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
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
        FacturaElectronica.objects.create(
            venta=venta,
            cufe='CUFE-002',
            uuid='UUID-002',
            number='SETP-101',
            reference_code='SETP-101',
            status='ACEPTADA',
            xml_url='https://example.com/invoice.xml',
            pdf_url='https://example.com/invoice.pdf',
            response_json={},
        )
        mocked_create_credit_note.side_effect = FactusAPIError('timeout')
        stock_inicial = self.producto.stock

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {'motivo': 'DEVOLUCION_TOTAL', 'descripcion': 'test'},
            format='json',
        )
        self.assertEqual(response.status_code, 502)
        venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')
        self.assertEqual(self.producto.stock, stock_inicial)

    @patch('apps.ventas.services.anular_venta.create_credit_note')
    def test_anular_factura_electronica_no_aceptada_no_anula_venta(self, mocked_create_credit_note):
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
            estado='FACTURADA',
            inventario_ya_afectado=True,
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
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
        FacturaElectronica.objects.create(
            venta=venta,
            cufe='CUFE-003',
            uuid='UUID-003',
            number='SETP-102',
            reference_code='SETP-102',
            status='ACEPTADA',
            xml_url='https://example.com/invoice.xml',
            pdf_url='https://example.com/invoice.pdf',
            response_json={},
        )
        mocked_create_credit_note.return_value = (MagicMock(id=11, number='NC-002', estado_local='PENDIENTE_DIAN'), {'result': 'pending_dian', 'ok': True, 'finalized': False, 'business_effects_applied': False})
        stock_inicial = self.producto.stock

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {'motivo': 'DEVOLUCION_TOTAL', 'descripcion': 'test'},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')
        self.assertEqual(self.producto.stock, stock_inicial)

    @patch('apps.ventas.services.anular_venta.create_credit_note')
    def test_anular_factura_sin_electronica_aceptada_se_anula_local(self, mocked_create_credit_note):
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
            estado='FACTURADA',
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
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
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {'motivo': 'ERROR_SISTEMA', 'descripcion': 'test'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        mocked_create_credit_note.assert_not_called()
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'ANULADA')

    def test_anular_no_restituye_inventario_si_no_hubo_salida_real(self):
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
            estado='FACTURADA',
            inventario_ya_afectado=False,
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
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
        stock_inicial = self.producto.stock

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {'motivo': 'ERROR_SISTEMA', 'descripcion': 'test'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, stock_inicial)

    def test_anular_con_devuelve_inventario_false_no_crea_movimiento_devolucion(self):
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
            estado='FACTURADA',
            inventario_ya_afectado=True,
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
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
        stock_inicial = self.producto.stock

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {'motivo': 'DEVOLUCION_TOTAL', 'descripcion': 'test', 'devuelve_inventario': False},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'ANULADA')
        self.assertEqual(self.producto.stock, stock_inicial)
        self.assertFalse(
            MovimientoInventario.objects.filter(
                tipo='DEVOLUCION',
                referencia=f'Anulación {venta.numero_comprobante}',
            ).exists()
        )

    @patch('apps.ventas.views.facturar_venta')
    def test_caja_facturar_dispara_servicio_factus(self, mocked_facturar_venta):
        mocked_factura = MagicMock()
        mocked_factura.number = 'SETP-1001'
        mocked_factura.status = 'ACEPTADA'
        mocked_factura.cufe = 'CUFE-TEST'
        mocked_factura.uuid = 'UUID-TEST'
        mocked_factura.reference_code = 'SETP-1001'
        mocked_factura.response_json = {'request': {'send_email': False}}
        mocked_facturar_venta.return_value = mocked_factura

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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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
        self.assertTrue(response.data['factus_sent'])
        self.assertEqual(response.data['numero_factura'], 'SETP-1001')
        mocked_facturar_venta.assert_called_once_with(venta.id, triggered_by=self.cajero)

    @patch('apps.ventas.views.facturar_venta')
    def test_caja_facturar_error_factus_no_reporta_exito(self, mocked_facturar_venta):
        from apps.facturacion.services import FactusAPIError

        mocked_facturar_venta.side_effect = FactusAPIError('Factus caído')
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['factus_sent'])
        self.assertEqual(response.data['estado_electronico'], 'ERROR')

    @patch('apps.ventas.views.facturar_venta')
    def test_facturar_venta_retorna_200_con_advertencia_si_falla_emision_electronica(self, mocked_facturar_venta):
        from apps.facturacion.services import FactusAPIError

        mocked_facturar_venta.side_effect = FactusAPIError('Factus caído')
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
            estado='BORRADOR',
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
        response = self.client.post(f'/api/ventas/{venta.id}/facturar/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['ok'])
        self.assertFalse(response.data['factus_sent'])
        self.assertEqual(response.data['warning'], 'FACTURA_LOCAL_OK_EMISION_ELECTRONICA_FALLIDA')
        self.assertIn(response.data['estado_local'], {'COBRADA', 'FACTURADA'})

    @patch('apps.ventas.views.emitir_factura_completa')
    def test_facturar_venta_dataerror_retorna_respuesta_controlada(self, mocked_emitir_factura_completa):
        mocked_emitir_factura_completa.side_effect = DataError('value too long for type character varying(500)')
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
            estado='BORRADOR',
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
        response = self.client.post(f'/api/ventas/{venta.id}/facturar/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['ok'])
        self.assertEqual(response.data['error_code'], 'ERROR_PERSISTENCIA')
        self.assertIn('warnings', response.data)

    @patch('apps.ventas.views.emitir_factura_completa')
    def test_facturar_venta_retorna_resultado_electronico_pendiente_con_venta_local_cobrada(self, mocked_emitir_factura_completa):
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
            estado='BORRADOR',
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
        factura = FacturaElectronica.objects.create(
            venta=venta,
            number='SETP-PT-1',
            reference_code='SETP-PT-1',
            estado_electronico='PENDIENTE_REINTENTO',
            cufe='',
            uuid='',
            response_json={},
        )
        mocked_emitir_factura_completa.return_value = {'factura': factura, 'warnings': []}
        self.client.force_authenticate(user=self.vendedor)

        response = self.client.post(f'/api/ventas/{venta.id}/facturar/')

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['estado_local'], 'COBRADA')
        self.assertEqual(response.data['estado_electronico'], 'PENDIENTE_REINTENTO')
        self.assertEqual(response.data['resultado_electronico'], 'PENDIENTE')
        self.assertEqual(response.data['status'], 'PENDIENTE_REINTENTO')

    def test_facturaelectronica_save_status_legacy_se_deriva_desde_estado_electronico(self):
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
            estado='COBRADA',
        )
        factura = FacturaElectronica.objects.create(
            venta=venta,
            number='SETP-LEG-1',
            reference_code='SETP-LEG-1',
            estado_electronico='RECHAZADA',
            status='ACEPTADA',
            response_json={},
        )
        factura.refresh_from_db()
        self.assertEqual(factura.estado_electronico, 'RECHAZADA')
        self.assertEqual(factura.status, 'RECHAZADA')

    @patch('apps.ventas.views.emitir_factura_completa')
    def test_convertir_remision_dataerror_retorna_error_persistencia_controlado(self, mocked_emitir_factura_completa):
        mocked_emitir_factura_completa.side_effect = DataError('value too long for type character varying(2048)')
        remision = Venta.objects.create(
            tipo_comprobante='REMISION',
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
            estado='COBRADA',
        )
        DetalleVenta.objects.create(
            venta=remision,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )
        self.client.force_authenticate(user=self.vendedor)
        response = self.client.post(f'/api/ventas/{remision.id}/convertir_a_factura/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['ok'])
        self.assertEqual(response.data['error_code'], 'ERROR_PERSISTENCIA')
        self.assertEqual(response.data['estado_electronico'], 'ERROR_PERSISTENCIA')

    @patch('apps.ventas.views.emitir_factura_completa')
    def test_convertir_remision_no_contamina_consecutivo_remision(self, mocked_emitir_factura_completa):
        remision = Venta.objects.create(
            tipo_comprobante='REMISION',
            numero_comprobante='REM-154239',
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
            estado='COBRADA',
        )
        DetalleVenta.objects.create(
            venta=remision,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )
        factura_e = FacturaElectronica.objects.create(
            venta=Venta.objects.create(
                tipo_comprobante='FACTURA',
                numero_comprobante=None,
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
                estado='COBRADA',
            ),
            number='SETP000123',
            reference_code='SETP000123',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            cufe='CUFE-123',
            uuid='UUID-123',
            response_json={'ok': True},
        )
        mocked_emitir_factura_completa.return_value = {'factura': factura_e, 'warnings': []}
        self.client.force_authenticate(user=self.vendedor)
        response = self.client.post(f'/api/ventas/{remision.id}/convertir_a_factura/')
        self.assertEqual(response.status_code, 201)
        remision.refresh_from_db()
        self.assertEqual(remision.numero_comprobante, 'REM-154239')
        factura_destino = Venta.objects.get(remision_origen=remision)
        self.assertIsNone(factura_destino.numero_comprobante)

    @patch('apps.ventas.views.facturar_venta')
    def test_facturar_venta_retorna_advertencia_de_datos_cliente(self, mocked_facturar_venta):
        from apps.facturacion.services import FactusValidationError

        mocked_facturar_venta.side_effect = FactusValidationError(
            'El cliente seleccionado no tiene número de identificación configurado para facturación electrónica.'
        )
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
            estado='BORRADOR',
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
        response = self.client.post(f'/api/ventas/{venta.id}/facturar/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['ok'])
        self.assertEqual(response.data['warning'], 'FACTURA_LOCAL_OK_DATOS_CLIENTE_INVALIDOS')

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

    def test_caja_factura_venta_con_descuento_global(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.vendedor,
            subtotal=Decimal('80'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('6.40'),
            iva=Decimal('15.20'),
            total=Decimal('88.80'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('90'),
            cambio=Decimal('1.20'),
            estado='ENVIADA_A_CAJA',
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=2,
            precio_unitario=Decimal('30'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('60'),
            total=Decimal('71.40'),
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=2,
            precio_unitario=Decimal('10'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('20'),
            total=Decimal('23.80'),
        )

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(f'/api/caja/{venta.id}/facturar/')
        self.assertEqual(response.status_code, 200)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')

    def test_enviar_a_caja_valida_totales_en_backend(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.vendedor,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='BORRADOR',
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
        response = self.client.post(f'/api/ventas/{venta.id}/enviar-a-caja/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('no coincide', str(response.data.get('error')))

    def test_facturar_venta_origen_taller_no_descuenta_doble(self):
        MovimientoInventario.objects.create(
            producto=self.producto,
            tipo='SALIDA',
            cantidad=Decimal('-1'),
            stock_anterior=Decimal('10'),
            stock_nuevo=Decimal('9'),
            costo_unitario=Decimal('100'),
            usuario=self.vendedor,
            referencia='Orden taller #1',
            observaciones='Salida por orden de taller',
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, Decimal('9'))

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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
            inventario_ya_afectado=True,
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
        self.producto.refresh_from_db()

        self.assertEqual(venta.estado, 'FACTURADA')
        self.assertTrue(venta.inventario_ya_afectado)
        self.assertEqual(self.producto.stock, Decimal('9'))
        self.assertEqual(MovimientoInventario.objects.count(), 1)

    def test_anular_venta_origen_taller_devuelve_stock_una_vez(self):
        MovimientoInventario.objects.create(
            producto=self.producto,
            tipo='SALIDA',
            cantidad=Decimal('-1'),
            stock_anterior=Decimal('10'),
            stock_nuevo=Decimal('9'),
            costo_unitario=Decimal('100'),
            usuario=self.vendedor,
            referencia='Orden taller #2',
            observaciones='Salida por orden de taller',
        )
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
            estado='FACTURADA',
            inventario_ya_afectado=True,
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
        response = self.client.post(
            f'/api/ventas/{venta.id}/anular/',
            {
                'motivo': 'DEVOLUCION_TOTAL',
                'descripcion': 'Anulación prueba',
                'devuelve_inventario': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.producto.refresh_from_db()

        self.assertEqual(self.producto.stock, Decimal('10'))
        self.assertEqual(MovimientoInventario.objects.filter(tipo='DEVOLUCION').count(), 1)

    def test_caja_pendientes_solo_incluye_ventas_enviadas_y_no_facturadas(self):
        enviada = Venta.objects.create(
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
        )
        DetalleVenta.objects.create(
            venta=enviada,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )

        facturada = Venta.objects.create(
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
            estado='FACTURADA',
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
            facturada_por=self.cajero,
            facturada_at=timezone.now(),
        )
        DetalleVenta.objects.create(
            venta=facturada,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )

        remision = Venta.objects.create(
            tipo_comprobante='REMISION',
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
        )
        DetalleVenta.objects.create(
            venta=remision,
            producto=self.producto,
            cantidad=1,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )

        self.client.force_authenticate(user=self.cajero)
        response = self.client.get('/api/caja/pendientes/')
        self.assertEqual(response.status_code, 200)
        ids = [item['id'] for item in response.data]
        self.assertIn(enviada.id, ids)
        self.assertNotIn(facturada.id, ids)
        self.assertNotIn(remision.id, ids)

    def test_vendedor_no_puede_ver_pendientes_caja(self):
        self.client.force_authenticate(user=self.vendedor)
        response = self.client.get('/api/caja/pendientes/')
        self.assertEqual(response.status_code, 403)

    def test_caja_puede_obtener_detalle_pendiente(self):
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
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
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
        response = self.client.get(f'/api/caja/{venta.id}/detalle/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], venta.id)
        self.assertEqual(response.data['estado'], 'ENVIADA_A_CAJA')
        self.assertEqual(len(response.data['detalles']), 1)

    def test_detalle_caja_rechaza_ventas_no_pendientes(self):
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
            estado='BORRADOR',
        )

        self.client.force_authenticate(user=self.cajero)
        response = self.client.get(f'/api/caja/{venta.id}/detalle/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('no está disponible para cargarse en caja', response.data['error'])

    def test_facturar_en_caja_permite_stock_negativo_y_registra_movimiento(self):
        self.producto.stock = Decimal('1')
        self.producto.save(update_fields=['stock'])

        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.vendedor,
            subtotal=Decimal('400'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('76'),
            total=Decimal('476'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('500'),
            cambio=Decimal('24'),
            estado='ENVIADA_A_CAJA',
            enviada_a_caja_por=self.vendedor,
            enviada_a_caja_at=timezone.now(),
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=2,
            precio_unitario=Decimal('200'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('400'),
            total=Decimal('476'),
        )

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(f'/api/caja/{venta.id}/facturar/')
        self.assertEqual(response.status_code, 200)

        venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(venta.estado, 'FACTURADA')
        self.assertTrue(venta.inventario_ya_afectado)
        self.assertIsNotNone(venta.facturada_at)
        self.assertEqual(venta.facturada_por, self.cajero)
        self.assertEqual(self.producto.stock, Decimal('-1'))
        movimiento = MovimientoInventario.objects.get()
        self.assertEqual(movimiento.stock_anterior, Decimal('1'))
        self.assertEqual(movimiento.stock_nuevo, Decimal('-1'))
        self.assertIn('stock negativo permitido', movimiento.observaciones.lower())


class VentaIVAIncluidoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vendedor = Usuario.objects.create_user(
            username='vendedor_iva',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.client.force_authenticate(user=self.vendedor)

        self.categoria = Categoria.objects.create(nombre='IVA incluido')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor IVA')
        self.producto_gravado = Producto.objects.create(
            codigo='IVA-001',
            nombre='Producto gravado',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('3000.00'),
            precio_venta_minimo=Decimal('2500.00'),
            stock=Decimal('50.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=False,
        )
        self.producto_legacy_0365 = Producto.objects.create(
            codigo='0365',
            nombre='ORING 08 (MEDIANO)',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('300.00'),
            precio_venta=Decimal('600.00'),
            precio_venta_minimo=Decimal('500.00'),
            stock=Decimal('93.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=False,
        )
        self.producto_exento = Producto.objects.create(
            codigo='IVA-EX-001',
            nombre='Producto exento',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('3000.00'),
            precio_venta_minimo=Decimal('2500.00'),
            stock=Decimal('50.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=True,
        )
        self.cliente = Cliente.objects.create(
            tipo_documento='CC',
            numero_documento='900001',
            nombre='Cliente IVA',
        )

    def _payload_base(self, detalles):
        return {
            'tipo_comprobante': 'FACTURA',
            'cliente': self.cliente.id,
            'vendedor': self.vendedor.id,
            'subtotal': '0.00',
            'descuento_porcentaje': '0',
            'descuento_valor': '0',
            'iva': '0.00',
            'total': '0.00',
            'medio_pago': 'EFECTIVO',
            'efectivo_recibido': '10000.00',
            'cambio': '0',
            'detalles': detalles,
        }

    def test_creacion_venta_iva_incluido(self):
        payload = self._payload_base([
            {
                'producto': self.producto_gravado.id,
                'cantidad': '1',
                'precio_unitario': '3000.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        venta = Venta.objects.get(id=response.data['id'])
        detalle = venta.detalles.get()

        self.assertEqual(detalle.total, Decimal('3000.00'))
        self.assertEqual(detalle.subtotal, Decimal('2521.01'))
        self.assertEqual(venta.subtotal, Decimal('2521.01'))
        self.assertEqual(venta.iva, Decimal('478.99'))
        self.assertEqual(venta.total, Decimal('3000.00'))

    def test_actualizacion_venta_iva_incluido(self):
        create_payload = self._payload_base([
            {
                'producto': self.producto_gravado.id,
                'cantidad': '1',
                'precio_unitario': '3000.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        create_response = self.client.post('/api/ventas/', create_payload, format='json')
        self.assertEqual(create_response.status_code, 201, create_response.data)

        update_payload = {
            'detalles': [
                {
                    'producto': self.producto_gravado.id,
                    'cantidad': '2',
                    'precio_unitario': '3000.00',
                    'descuento_unitario': '0.00',
                    'iva_porcentaje': '19.00',
                }
            ]
        }
        response = self.client.patch(
            f"/api/ventas/{create_response.data['id']}/",
            update_payload,
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        venta = Venta.objects.get(id=create_response.data['id'])
        detalle = venta.detalles.get()
        self.assertEqual(detalle.total, Decimal('6000.00'))
        self.assertEqual(detalle.subtotal, Decimal('5042.02'))
        self.assertEqual(venta.subtotal, Decimal('5042.02'))
        self.assertEqual(venta.iva, Decimal('957.98'))
        self.assertEqual(venta.total, Decimal('6000.00'))

    def test_patch_ignora_totales_manual_y_recalcula_desde_detalles(self):
        create_payload = self._payload_base([
            {
                'producto': self.producto_gravado.id,
                'cantidad': '1',
                'precio_unitario': '3000.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        create_response = self.client.post('/api/ventas/', create_payload, format='json')
        self.assertEqual(create_response.status_code, 201, create_response.data)
        venta_id = create_response.data['id']

        response = self.client.patch(
            f"/api/ventas/{venta_id}/",
            {
                'subtotal': '1.00',
                'iva': '1.00',
                'total': '1.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)

        venta = Venta.objects.get(id=venta_id)
        self.assertEqual(venta.subtotal, Decimal('2521.01'))
        self.assertEqual(venta.iva, Decimal('478.99'))
        self.assertEqual(venta.total, Decimal('3000.00'))

    def test_descuento_por_linea_iva_incluido(self):
        payload = self._payload_base([
            {
                'producto': self.producto_gravado.id,
                'cantidad': '2',
                'precio_unitario': '3000.00',
                'descuento_unitario': '500.00',
                'iva_porcentaje': '19.00',
            }
        ])
        response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        venta = Venta.objects.get(id=response.data['id'])
        detalle = venta.detalles.get()

        self.assertEqual(detalle.total, Decimal('5000.00'))
        self.assertEqual(detalle.subtotal, Decimal('4201.68'))
        self.assertEqual(venta.subtotal, Decimal('4201.68'))
        self.assertEqual(venta.iva, Decimal('798.32'))
        self.assertEqual(venta.total, Decimal('5000.00'))

    def test_producto_exento(self):
        payload = self._payload_base([
            {
                'producto': self.producto_exento.id,
                'cantidad': '1',
                'precio_unitario': '3000.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        venta = Venta.objects.get(id=response.data['id'])
        detalle = venta.detalles.get()

        self.assertEqual(detalle.total, Decimal('3000.00'))
        self.assertEqual(detalle.subtotal, Decimal('3000.00'))
        self.assertEqual(venta.subtotal, Decimal('3000.00'))
        self.assertEqual(venta.iva, Decimal('0.00'))
        self.assertEqual(venta.total, Decimal('3000.00'))

    def test_borrador_enviar_a_caja_consistente(self):
        payload = self._payload_base([
            {
                'producto': self.producto_gravado.id,
                'cantidad': '1',
                'precio_unitario': '3000.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        create_response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(create_response.status_code, 201, create_response.data)

        venta_id = create_response.data['id']
        response = self.client.post(f'/api/ventas/{venta_id}/enviar-a-caja/')
        self.assertEqual(response.status_code, 200, response.data)

        venta = Venta.objects.get(id=venta_id)
        self.assertEqual(venta.estado, 'ENVIADA_A_CAJA')
        self.assertEqual(venta.subtotal + venta.iva - venta.descuento_valor, venta.total)

    def test_flujo_vendedor_caja_facturar_conserva_totales_originales(self):
        payload = self._payload_base([
            {
                'producto': self.producto_gravado.id,
                'cantidad': '1',
                'precio_unitario': '3000.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        create_response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(create_response.status_code, 201, create_response.data)
        venta_id = create_response.data['id']

        patch_response = self.client.patch(
            f'/api/ventas/{venta_id}/',
            {'total': '10000.00', 'subtotal': '10000.00', 'iva': '0.00'},
            format='json',
        )
        self.assertEqual(patch_response.status_code, 200, patch_response.data)

        enviar_response = self.client.post(f'/api/ventas/{venta_id}/enviar-a-caja/')
        self.assertEqual(enviar_response.status_code, 200, enviar_response.data)

        venta = Venta.objects.get(id=venta_id)
        self.assertEqual(venta.subtotal, Decimal('2521.01'))
        self.assertEqual(venta.iva, Decimal('478.99'))
        self.assertEqual(venta.total, Decimal('3000.00'))

    def test_producto_legacy_0365_cantidad_1(self):
        payload = self._payload_base([
            {
                'producto': self.producto_legacy_0365.id,
                'cantidad': '1',
                'precio_unitario': '600.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        venta = Venta.objects.get(id=response.data['id'])
        detalle = venta.detalles.get()
        self.assertEqual(detalle.total, Decimal('600.00'))
        self.assertEqual(detalle.subtotal, Decimal('504.20'))
        self.assertEqual(venta.subtotal, Decimal('504.20'))
        self.assertEqual(venta.iva, Decimal('95.80'))
        self.assertEqual(venta.total, Decimal('600.00'))
        self.assertEqual(venta.subtotal + venta.iva - venta.descuento_valor, venta.total)

    def test_producto_legacy_0365_cantidad_2(self):
        payload = self._payload_base([
            {
                'producto': self.producto_legacy_0365.id,
                'cantidad': '2',
                'precio_unitario': '600.00',
                'descuento_unitario': '0.00',
                'iva_porcentaje': '19.00',
            }
        ])
        response = self.client.post('/api/ventas/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        venta = Venta.objects.get(id=response.data['id'])
        detalle = venta.detalles.get()
        self.assertEqual(detalle.total, Decimal('1200.00'))
        self.assertEqual(detalle.subtotal, Decimal('1008.40'))
        self.assertEqual(venta.subtotal, Decimal('1008.40'))
        self.assertEqual(venta.iva, Decimal('191.60'))
        self.assertEqual(venta.total, Decimal('1200.00'))


class PosTicketDiscriminacionIvaTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(username='ticket-user', password='pass1234', tipo_usuario='ADMIN')
        categoria = Categoria.objects.create(nombre='Ticket Cat')
        proveedor = Proveedor.objects.create(nombre='Ticket Prov')
        self.producto = Producto.objects.create(
            codigo='TCK-1',
            nombre='Producto Ticket',
            categoria=categoria,
            proveedor=proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('3000.00'),
            precio_venta_minimo=Decimal('2500.00'),
            stock=Decimal('10'),
            stock_minimo=Decimal('1'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=False,
        )
        self.cliente = Cliente.objects.create(tipo_documento='CC', numero_documento='1000', nombre='Cliente Ticket')

    def test_discriminacion_iva_se_construye_desde_detalles(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FV-TEST-1',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('5042.02'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('957.98'),
            total=Decimal('6000.00'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('6000.00'),
            cambio=Decimal('0'),
            estado='COBRADA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto,
            cantidad=Decimal('2'),
            precio_unitario=Decimal('3000.00'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19.00'),
            subtotal=Decimal('5042.02'),
            total=Decimal('6000.00'),
        )
        factura = FacturaElectronica.objects.create(
            venta=venta,
            cufe='CUFE-1',
            uuid='UUID-1',
            number='FV-TEST-1',
            reference_code='FV-TEST-1',
            status='ACEPTADA',
            xml_url='https://example.com/x.xml',
            pdf_url='https://example.com/x.pdf',
            response_json={},
        )

        payload = build_pos_ticket_payload(venta, factura)
        self.assertEqual(payload['items'][0]['subtotal'], 5042.02)
        self.assertEqual(payload['items'][0]['iva_valor'], 957.98)
        self.assertEqual(payload['discriminacion_iva'][0]['tarifa'], 19.0)
        self.assertEqual(payload['discriminacion_iva'][0]['base_imp'], 5042.02)
        self.assertEqual(payload['discriminacion_iva'][0]['valor_iva'], 957.98)
        self.assertEqual(payload['discriminacion_iva'][0]['valor_compra'], 6000.0)


class EmisionFacturaUseCaseAndViewDelegationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vendedor = Usuario.objects.create_user(username='uc-vendedor', password='pass1234', tipo_usuario='VENDEDOR')
        self.cajero = Usuario.objects.create_user(username='uc-cajero', password='pass1234', tipo_usuario='VENDEDOR')
        self.cajero.es_cajero = True
        self.cajero.save(update_fields=['es_cajero'])
        categoria = Categoria.objects.create(nombre='UC Cat')
        proveedor = Proveedor.objects.create(nombre='UC Prov')
        self.producto = Producto.objects.create(
            codigo='UC-1',
            nombre='Producto UC',
            categoria=categoria,
            proveedor=proveedor,
            precio_costo=Decimal('100'),
            precio_venta=Decimal('200'),
            precio_venta_minimo=Decimal('150'),
            stock=10,
            stock_minimo=1,
            iva_porcentaje=Decimal('19'),
        )
        self.cliente = Cliente.objects.create(tipo_documento='CC', numero_documento='987654', nombre='Cliente UC')

    def _crear_venta(self, estado='BORRADOR'):
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
            estado=estado,
            enviada_a_caja_por=self.vendedor if estado == 'ENVIADA_A_CAJA' else None,
            enviada_a_caja_at=timezone.now() if estado == 'ENVIADA_A_CAJA' else None,
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
        return venta

    @patch('apps.facturacion.use_cases.emit_invoice_use_case.emitir_factura_completa')
    def test_use_case_venta_cobrada_factura_aceptada(self, mocked_emitir):
        from apps.facturacion.use_cases import emit_invoice_use_case

        venta = self._crear_venta()
        factura = FacturaElectronica.objects.create(venta=venta, number='FAC-OK-1', reference_code='REF-OK-1', estado_electronico='ACEPTADA', response_json={})
        mocked_emitir.return_value = {'factura': factura, 'warnings': []}

        result = emit_invoice_use_case(venta_id=venta.id, triggered_by=self.vendedor)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'COBRADA')
        self.assertEqual(result.factura.estado_electronico, 'ACEPTADA')

    @patch('apps.facturacion.use_cases.emit_invoice_use_case.emitir_factura_completa')
    def test_use_case_venta_cobrada_factura_pendiente(self, mocked_emitir):
        from apps.facturacion.use_cases import emit_invoice_use_case

        venta = self._crear_venta()
        factura = FacturaElectronica.objects.create(venta=venta, number='FAC-PEN-1', reference_code='REF-PEN-1', estado_electronico='PENDIENTE_REINTENTO', response_json={})
        mocked_emitir.return_value = {'factura': factura, 'warnings': []}

        result = emit_invoice_use_case(venta_id=venta.id, triggered_by=self.vendedor)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'COBRADA')
        self.assertEqual(result.factura.estado_electronico, 'PENDIENTE_REINTENTO')

    @patch('apps.facturacion.use_cases.emit_invoice_use_case.emitir_factura_completa')
    def test_use_case_venta_cobrada_factura_rechazada(self, mocked_emitir):
        from apps.facturacion.use_cases import emit_invoice_use_case

        venta = self._crear_venta()
        factura = FacturaElectronica.objects.create(venta=venta, number='FAC-REJ-1', reference_code='REF-REJ-1', estado_electronico='RECHAZADA', response_json={})
        mocked_emitir.return_value = {'factura': factura, 'warnings': []}

        result = emit_invoice_use_case(venta_id=venta.id, triggered_by=self.vendedor)
        venta.refresh_from_db()
        self.assertEqual(venta.estado, 'COBRADA')
        self.assertEqual(result.factura.estado_electronico, 'RECHAZADA')

    @patch('apps.facturacion.use_cases.emit_invoice_use_case.emitir_factura_completa')
    def test_use_case_reintento_no_duplica_reference_code(self, mocked_emitir):
        from apps.facturacion.use_cases import emit_invoice_use_case

        venta = self._crear_venta(estado='COBRADA')
        factura = FacturaElectronica.objects.create(venta=venta, number='FAC-RET-1', reference_code='REF-RET-1', estado_electronico='PENDIENTE_REINTENTO', response_json={})
        mocked_emitir.return_value = {'factura': factura, 'warnings': []}

        first = emit_invoice_use_case(venta_id=venta.id, triggered_by=self.vendedor)
        second = emit_invoice_use_case(venta_id=venta.id, triggered_by=self.vendedor)

        self.assertEqual(first.factura.reference_code, second.factura.reference_code)
        self.assertEqual(FacturaElectronica.objects.filter(venta=venta).count(), 1)

    @patch('apps.ventas.views.emit_invoice_use_case')
    def test_view_ventas_facturar_delega_use_case(self, mocked_use_case):
        from apps.facturacion.use_cases import EmitInvoiceResult

        venta = self._crear_venta()
        factura = FacturaElectronica.objects.create(venta=venta, number='FAC-VIEW-1', reference_code='REF-VIEW-1', estado_electronico='ACEPTADA', response_json={})
        mocked_use_case.return_value = EmitInvoiceResult(venta=venta, factura=factura, warnings=[])

        self.client.force_authenticate(user=self.vendedor)
        response = self.client.post(f'/api/ventas/{venta.id}/facturar/')
        self.assertIn(response.status_code, {200, 201})
        mocked_use_case.assert_called()

    @patch('apps.ventas.views.emit_invoice_use_case')
    def test_view_caja_facturar_delega_use_case(self, mocked_use_case):
        from apps.facturacion.use_cases import EmitInvoiceResult

        venta = self._crear_venta(estado='ENVIADA_A_CAJA')
        factura = FacturaElectronica.objects.create(venta=venta, number='FAC-CAJA-1', reference_code='REF-CAJA-1', estado_electronico='ACEPTADA', response_json={})
        mocked_use_case.return_value = EmitInvoiceResult(venta=venta, factura=factura, warnings=[])

        self.client.force_authenticate(user=self.cajero)
        response = self.client.post(f'/api/caja/{venta.id}/facturar/')
        self.assertEqual(response.status_code, 200)
        mocked_use_case.assert_called()
