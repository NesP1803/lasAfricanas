from __future__ import annotations

import tempfile
import os
from decimal import Decimal
from pathlib import Path
from io import StringIO
from unittest.mock import MagicMock, patch

from apps.facturacion.exceptions import DocumentoSoporteInvalido

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.facturacion.models import DocumentoSoporteElectronico, FacturaElectronica, NotaCreditoElectronica
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.support_document_payload_builder import build_support_document_payload
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusValidationError
from apps.core.models import Impuesto
from apps.inventario.models import Categoria, Producto, Proveedor
from apps.ventas.models import Cliente, DetalleVenta, Venta
from apps.facturacion.models import RangoNumeracionDIAN


class FacturaDownloadFilesTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        User = get_user_model()
        self.user = User.objects.create_user(username='vendedor', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='123', nombre='Cliente Test')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-1',
            uuid='UUID-1',
            number='FV1234',
            reference_code='FV1234',
            status='ACEPTADA',
            xml_url='https://example.com/fv1234.xml',
            pdf_url='https://example.com/fv1234.pdf',
            qr='qr',
            response_json={'ok': True},
        )

    def test_download_xml(self):
        with override_settings(MEDIA_ROOT=self.tmpdir.name):
            mocked = MagicMock()
            mocked.content = b'<xml>ok</xml>'
            mocked.raise_for_status.return_value = None
            with patch('apps.facturacion.services.download_invoice_files.requests.get', return_value=mocked):
                result = download_xml(self.factura)

            self.assertEqual(result, 'facturas/xml/FV1234.xml')
            self.factura.refresh_from_db()
            self.assertEqual(self.factura.xml_local_path, 'facturas/xml/FV1234.xml')
            self.assertTrue((Path(self.tmpdir.name) / result).exists())

    def test_download_pdf_url_vacia_lanza_error(self):
        self.factura.pdf_url = ''
        self.factura.save(update_fields=['pdf_url'])

        with self.assertRaises(DescargaFacturaError):
            download_pdf(self.factura)


class FacturaFilesEndpointsTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        User = get_user_model()
        self.user = User.objects.create_user(username='cajero', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.cliente = Cliente.objects.create(numero_documento='456', nombre='Cliente Endpoint')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-2',
            uuid='UUID-2',
            number='FV9999',
            reference_code='FV9999',
            status='ACEPTADA',
            xml_url='https://example.com/fv9999.xml',
            pdf_url='https://example.com/fv9999.pdf',
            xml_local_path='facturas/xml/FV9999.xml',
            pdf_local_path='facturas/pdf/FV9999.pdf',
            qr='qr',
            response_json={'ok': True},
        )
        (Path(self.tmpdir.name) / 'facturas/xml').mkdir(parents=True, exist_ok=True)
        (Path(self.tmpdir.name) / 'facturas/pdf').mkdir(parents=True, exist_ok=True)
        (Path(self.tmpdir.name) / 'facturas/xml/FV9999.xml').write_bytes(b'<xml>factura</xml>')
        (Path(self.tmpdir.name) / 'facturas/pdf/FV9999.pdf').write_bytes(b'%PDF-factura')

    def test_xml_endpoint(self):
        with override_settings(MEDIA_ROOT=self.tmpdir.name):
            response = self.client.get('/api/facturacion/FV9999/xml/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertIn('attachment; filename="factura-FV9999.xml"', response['Content-Disposition'])
        self.assertEqual(response.content, b'<xml>factura</xml>')

    def test_pdf_endpoint(self):
        with override_settings(MEDIA_ROOT=self.tmpdir.name):
            response = self.client.get('/api/facturacion/FV9999/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="factura-FV9999.pdf"', response['Content-Disposition'])
        self.assertEqual(response.content, b'%PDF-factura')

    def test_xml_endpoint_legacy(self):
        response = self.client.get('/api/facturacion/FV9999/xml/?legacy=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['xml'], 'facturas/xml/FV9999.xml')

    def test_list_endpoint(self):
        response = self.client.get('/api/facturacion/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['numero'], 'FV9999')
        self.assertEqual(response.data[0]['cliente'], 'Cliente Endpoint')
        self.assertEqual(response.data[0]['estado_dian'], 'ACEPTADA')

    @patch('apps.facturacion.views.send_mail')
    def test_enviar_correo_endpoint(self, mocked_send_mail):
        self.venta.cliente.email = 'cliente@example.com'
        self.venta.cliente.save(update_fields=['email'])

        response = self.client.post('/api/facturacion/FV9999/enviar-correo/')
        self.assertEqual(response.status_code, 200)
        mocked_send_mail.assert_called_once()

    def test_enviar_correo_endpoint_sin_email(self):
        response = self.client.post('/api/facturacion/FV9999/enviar-correo/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('no tiene correo configurado', response.data['detail'])


class FacturaQRYPosEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='pos', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.cliente = Cliente.objects.create(numero_documento='789', nombre='Cliente POS')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FV5555',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-3',
            uuid='UUID-3',
            number='FV5555',
            reference_code='FV5555',
            status='ACEPTADA',
            xml_url='https://example.com/fv5555.xml',
            pdf_url='https://example.com/fv5555.pdf',
            qr='facturas/qr/FV5555.png',
            response_json={'ok': True},
        )

    def test_qr_endpoint(self):
        response = self.client.get('/api/facturacion/FV5555/qr/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['numero'], 'FV5555')
        self.assertIn('/media/facturas/qr/FV5555.png', response.data['qr'])

    def test_pos_endpoint(self):
        response = self.client.get('/api/facturacion/FV5555/pos/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['numero'], 'FV5555')
        self.assertEqual(response.data['cliente'], 'Cliente POS')
        self.assertEqual(response.data['nit_cliente'], '789')
        self.assertEqual(response.data['cufe'], 'CUFE-3')


class DocumentoSoporteBuilderTests(TestCase):
    def test_valida_proveedor_documento_requerido(self):
        with self.assertRaises(DocumentoSoporteInvalido):
            build_support_document_payload(
                {
                    'proveedor_nombre': 'Juan Perez',
                    'items': [{'descripcion': 'Servicio', 'cantidad': 1, 'precio': 10000}],
                }
            )

    def test_valida_total_mayor_a_cero(self):
        with self.assertRaises(DocumentoSoporteInvalido):
            build_support_document_payload(
                {
                    'proveedor_nombre': 'Juan Perez',
                    'proveedor_documento': '123',
                    'proveedor_tipo_documento': 'CC',
                    'items': [{'descripcion': 'Servicio', 'cantidad': 1, 'precio': 0}],
                }
            )


class DocumentoSoporteEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='doc-soporte', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('apps.facturacion.views.emitir_documento_soporte')
    def test_endpoint_documento_soporte(self, mocked_emitir):
        mocked_emitir.return_value = MagicMock(number='DS123', cufe='CUFE-DS-1', status='ACEPTADA')

        payload = {
            'proveedor_nombre': 'Juan Perez',
            'proveedor_documento': '12345678',
            'proveedor_tipo_documento': 'CC',
            'items': [{'descripcion': 'Servicio técnico', 'cantidad': 1, 'precio': 100000}],
        }
        response = self.client.post('/api/facturacion/documento-soporte/', payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['numero'], 'DS123')
        self.assertEqual(response.data['cufe'], 'CUFE-DS-1')
        self.assertEqual(response.data['estado'], 'ACEPTADA')


class SyncInvoiceStatusCommandTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='sync-status', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='111', nombre='Cliente Sync')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )

    @patch('apps.facturacion.management.commands.sync_invoice_status.sync_invoice_status')
    def test_sync_invoice_status_incluye_en_proceso_y_pendiente(self, mocked_sync):
        factura_en_proceso = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-SYNC-1',
            uuid='UUID-SYNC-1',
            number='FV-SYNC-1',
            reference_code='FV-SYNC-1',
            status='EN_PROCESO',
            xml_url='https://example.com/fv-sync-1.xml',
            pdf_url='https://example.com/fv-sync-1.pdf',
            response_json={'ok': True},
        )
        venta_2 = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )
        factura_pendiente = FacturaElectronica.objects.create(
            venta=venta_2,
            cufe='CUFE-SYNC-2',
            uuid='UUID-SYNC-2',
            number='FV-SYNC-2',
            reference_code='FV-SYNC-2',
            status='PENDIENTE',
            xml_url='https://example.com/fv-sync-2.xml',
            pdf_url='https://example.com/fv-sync-2.pdf',
            response_json={'ok': True},
        )
        mocked_sync.side_effect = [factura_en_proceso, factura_pendiente]

        stdout = StringIO()
        call_command('sync_invoice_status', stdout=stdout)

        called_numbers = [call.args[0] for call in mocked_sync.call_args_list]
        self.assertCountEqual(called_numbers, ['FV-SYNC-1', 'FV-SYNC-2'])


class NotasCreditoResourceEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='nota-api', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.cliente = Cliente.objects.create(numero_documento='NC-CLIENTE', nombre='Cliente NC')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-NC',
            uuid='UUID-NC',
            number='FV-NC',
            reference_code='FV-NC',
            status='ACEPTADA',
            xml_url='https://example.com/fv-nc.xml',
            pdf_url='https://example.com/fv-nc.pdf',
            response_json={'ok': True},
        )
        self.nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            number='NC-001',
            uuid='UUID-NC-1',
            cufe='CUFE-NC-1',
            status='ACEPTADA',
            xml_url='https://example.com/nc-001.xml',
            pdf_url='https://example.com/nc-001.pdf',
            response_json={'credit_note_reason': 'Ajuste'},
        )

    def test_list_endpoint(self):
        response = self.client.get('/api/notas-credito/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['numero'], 'NC-001')
        self.assertEqual(response.data[0]['estado'], 'ACEPTADA')

    @patch('apps.facturacion.views.emitir_nota_credito')
    def test_create_endpoint(self, mocked_emitir):
        mocked_emitir.return_value = self.nota
        payload = {
            'factura_id': self.factura.id,
            'motivo': 'Devolución',
            'items': [{'descripcion': 'Item', 'cantidad': 1, 'precio': 1000}],
        }
        response = self.client.post('/api/notas-credito/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['numero'], 'NC-001')

    @patch('apps.facturacion.views.download_remote_file', return_value=b'<xml>nc</xml>')
    def test_xml_endpoint(self, mocked_download):
        response = self.client.get('/api/notas-credito/NC-001/xml/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response.content, b'<xml>nc</xml>')
        mocked_download.assert_called_once()

    @patch('apps.facturacion.views.download_remote_file', return_value=b'%PDF-nc')
    def test_pdf_endpoint(self, mocked_download):
        response = self.client.get('/api/notas-credito/NC-001/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content, b'%PDF-nc')
        mocked_download.assert_called_once()


class NumberingRangeResolutionTests(TestCase):
    def setUp(self):
        os.environ['FACTUS_ENV'] = 'sandbox'

    def test_fallback_cuando_hay_un_solo_rango_activo(self):
        rango = RangoNumeracionDIAN.objects.create(
            factus_range_id=8,
            environment='SANDBOX',
            document_code='FACTURA_VENTA',
            is_active_remote=True,
            is_selected_local=False,
            prefijo='SETP',
            desde=1,
            hasta=999999,
            resolucion='18760000001',
            consecutivo_actual=1,
            activo=True,
        )
        resolved = resolve_numbering_range(document_code='FACTURA_VENTA')
        self.assertEqual(resolved.id, rango.id)

    def test_error_cuando_hay_varios_activos_sin_seleccion(self):
        for idx in [8, 9]:
            RangoNumeracionDIAN.objects.create(
                factus_range_id=idx,
                environment='SANDBOX',
                document_code='FACTURA_VENTA',
                is_active_remote=True,
                is_selected_local=False,
                prefijo=f'SETP{idx}',
                desde=1,
                hasta=999999,
                resolucion='18760000001',
                consecutivo_actual=1,
                activo=True,
            )
        with self.assertRaises(FactusValidationError) as exc:
            resolve_numbering_range(document_code='FACTURA_VENTA')
        self.assertIn('múltiples rangos activos', str(exc.exception))

    def test_error_cuando_no_hay_rangos_sincronizados(self):
        with self.assertRaises(FactusValidationError) as exc:
            resolve_numbering_range(document_code='FACTURA_VENTA')
        self.assertIn('No hay rangos sincronizados', str(exc.exception))


class ConfiguracionDianRangosEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username='admin-rangos',
            password='1234',
            tipo_usuario='ADMIN',
            is_staff=True,
        )
        self.vendedor = User.objects.create_user(
            username='vendedor-rangos',
            password='1234',
            tipo_usuario='VENDEDOR',
        )
        self.rango = RangoNumeracionDIAN.objects.create(
            factus_range_id=8,
            environment='SANDBOX',
            document_code='FACTURA_VENTA',
            is_active_remote=True,
            is_selected_local=False,
            prefijo='SETP',
            desde=1,
            hasta=999999,
            resolucion='18760000001',
            consecutivo_actual=1,
            activo=True,
        )

    def test_select_rango_requiere_admin(self):
        client = APIClient()
        client.force_authenticate(self.vendedor)
        response = client.post('/api/configuracion/dian/rangos/select/', {'range_id': self.rango.id}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_admin_puede_seleccionar_rango(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post('/api/configuracion/dian/rangos/select/', {'range_id': self.rango.id}, format='json')
        self.assertEqual(response.status_code, 200)
        self.rango.refresh_from_db()
        self.assertTrue(self.rango.is_selected_local)

    @patch('apps.facturacion.views.sync_numbering_ranges')
    def test_sync_rangos_requiere_admin(self, mocked_sync):
        mocked_sync.return_value = [self.rango]
        client = APIClient()
        client.force_authenticate(self.vendedor)
        response = client.post('/api/configuracion/dian/rangos/sync/', {}, format='json')
        self.assertEqual(response.status_code, 403)


class DocumentosSoporteResourceEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='doc-api', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.documento = DocumentoSoporteElectronico.objects.create(
            number='DS-001',
            proveedor_nombre='Proveedor Test',
            proveedor_documento='900123',
            proveedor_tipo_documento='NIT',
            cufe='CUFE-DS-1',
            uuid='UUID-DS-1',
            status='ACEPTADA',
            xml_url='https://example.com/ds-001.xml',
            pdf_url='https://example.com/ds-001.pdf',
            response_json={'totals': {'total': 50000}},
        )

    def test_list_endpoint(self):
        response = self.client.get('/api/documentos-soporte/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['numero'], 'DS-001')
        self.assertEqual(response.data[0]['estado'], 'ACEPTADA')

    @patch('apps.facturacion.views.emitir_documento_soporte')
    def test_create_endpoint(self, mocked_emitir):
        mocked_emitir.return_value = self.documento
        payload = {
            'proveedor_nombre': 'Proveedor Nuevo',
            'proveedor_documento': '123',
            'proveedor_tipo_documento': 'CC',
            'items': [{'descripcion': 'Servicio', 'cantidad': 1, 'precio': 50000}],
        }
        response = self.client.post('/api/documentos-soporte/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['numero'], 'DS-001')

    @patch('apps.facturacion.views.download_remote_file', return_value=b'<xml>ds</xml>')
    def test_xml_endpoint(self, mocked_download):
        response = self.client.get('/api/documentos-soporte/DS-001/xml/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        self.assertEqual(response.content, b'<xml>ds</xml>')
        mocked_download.assert_called_once()

    @patch('apps.facturacion.views.download_remote_file', return_value=b'%PDF-ds')
    def test_pdf_endpoint(self, mocked_download):
        response = self.client.get('/api/documentos-soporte/DS-001/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content, b'%PDF-ds')
        mocked_download.assert_called_once()


class FacturaEstadoContratoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='estado-api', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(numero_documento='EST-1', nombre='Cliente Estado')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('100'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('19'),
            total=Decimal('119'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('119'),
            cambio=Decimal('0'),
            estado='FACTURADA',
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-EST',
            uuid='UUID-EST',
            number='FV-EST',
            reference_code='FV-EST',
            status='ACEPTADA',
            xml_url='https://example.com/fv-est.xml',
            pdf_url='https://example.com/fv-est.pdf',
            response_json={'ok': True},
        )

    @patch('apps.facturacion.views.sync_invoice_status')
    def test_estado_endpoint_incluye_campo_canonico(self, mocked_sync):
        mocked_sync.return_value = self.factura
        response = self.client.get('/api/facturacion/FV-EST/estado/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['estado'], 'ACEPTADA')
        self.assertEqual(response.data['estado_dian'], 'ACEPTADA')


class FactusInvoicePayloadIVAIncluidoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='payload-iva', password='1234')
        self.cliente = Cliente.objects.create(
            numero_documento='123456789',
            nombre='Cliente Payload',
            tipo_documento='CC',
        )
        self.categoria = Categoria.objects.create(nombre='Factus Payload')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor Payload')
        self.producto_gravado = Producto.objects.create(
            codigo='FP-001',
            nombre='Producto gravado',
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
            codigo='FP-EX-001',
            nombre='Producto exento',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('1000.00'),
            precio_venta=Decimal('3000.00'),
            precio_venta_minimo=Decimal('2500.00'),
            stock=Decimal('20.00'),
            stock_minimo=Decimal('1.00'),
            iva_porcentaje=Decimal('19.00'),
            iva_exento=True,
        )
        Impuesto.objects.create(
            nombre='IVA 19',
            porcentaje=Decimal('19.00'),
            factus_tribute_id=1,
            is_active=True,
        )

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_document_type_id', return_value=3)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_payload_customer_normaliza_identificacion(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_doc_type,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        self.cliente.numero_documento = ' 1.234.567-8 '
        self.cliente.save(update_fields=['numero_documento'])
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-900000',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('2521.01'),
            descuento_porcentaje=Decimal('0.00'),
            descuento_valor=Decimal('0.00'),
            iva=Decimal('478.99'),
            total=Decimal('3000.00'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('3000.00'),
            cambio=Decimal('0.00'),
            estado='FACTURADA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto_gravado,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('3000.00'),
            descuento_unitario=Decimal('0.00'),
            iva_porcentaje=Decimal('19.00'),
            subtotal=Decimal('2521.01'),
            total=Decimal('3000.00'),
        )
        payload = build_invoice_payload(venta)
        self.assertEqual(payload['customer']['identification'], '12345678')

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_document_type_id', return_value=3)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_payload_gravado_no_duplica_iva_con_precio_final(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_doc_type,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-900001',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('2521.01'),
            descuento_porcentaje=Decimal('0.00'),
            descuento_valor=Decimal('0.00'),
            iva=Decimal('478.99'),
            total=Decimal('3000.00'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('3000.00'),
            cambio=Decimal('0.00'),
            estado='FACTURADA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto_gravado,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('3000.00'),
            descuento_unitario=Decimal('0.00'),
            iva_porcentaje=Decimal('19.00'),
            subtotal=Decimal('2521.01'),
            total=Decimal('3000.00'),
        )

        payload = build_invoice_payload(venta)
        item = payload['items'][0]
        self.assertEqual(item['price'], 2521.01)
        self.assertEqual(item['tax_rate'], 19.0)
        self.assertEqual(item['is_excluded'], 0)
        self.assertEqual(item['quantity'], 1.0)
        self.assertEqual(round(item['price'] * item['quantity'], 2), 2521.01)
        self.assertEqual(round((item['price'] * item['quantity']) * (item['tax_rate'] / 100), 2), 478.99)
        self.assertEqual(round((item['price'] * item['quantity']) * (1 + item['tax_rate'] / 100), 2), 3000.0)

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_document_type_id', return_value=3)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_payload_exento_por_bandera_producto_envia_tax_rate_cero(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_doc_type,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-900002',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('3000.00'),
            descuento_porcentaje=Decimal('0.00'),
            descuento_valor=Decimal('0.00'),
            iva=Decimal('0.00'),
            total=Decimal('3000.00'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('3000.00'),
            cambio=Decimal('0.00'),
            estado='FACTURADA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto_exento,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('3000.00'),
            descuento_unitario=Decimal('0.00'),
            iva_porcentaje=Decimal('19.00'),
            subtotal=Decimal('3000.00'),
            total=Decimal('3000.00'),
        )

        payload = build_invoice_payload(venta)
        item = payload['items'][0]
        self.assertEqual(item['price'], 3000.0)
        self.assertEqual(item['tax_rate'], 0.0)
        self.assertEqual(item['is_excluded'], 1)

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_document_type_id', return_value=3)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_payload_producto_0365_precio_final_600(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_doc_type,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-900003',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('504.20'),
            descuento_porcentaje=Decimal('0.00'),
            descuento_valor=Decimal('0.00'),
            iva=Decimal('95.80'),
            total=Decimal('600.00'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('600.00'),
            cambio=Decimal('0.00'),
            estado='FACTURADA',
        )
        DetalleVenta.objects.create(
            venta=venta,
            producto=self.producto_gravado,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('600.00'),
            descuento_unitario=Decimal('0.00'),
            iva_porcentaje=Decimal('19.00'),
            subtotal=Decimal('504.20'),
            total=Decimal('600.00'),
        )

        payload = build_invoice_payload(venta)
        item = payload['items'][0]
        self.assertEqual(item['price'], 504.2)
        self.assertEqual(item['tax_rate'], 19.0)
        self.assertEqual(item['is_excluded'], 0)
        self.assertEqual(round(item['price'] * item['quantity'], 2), 504.2)
        self.assertEqual(round((item['price'] * item['quantity']) * (item['tax_rate'] / 100), 2), 95.8)
        self.assertEqual(round((item['price'] * item['quantity']) * (1 + item['tax_rate'] / 100), 2), 600.0)
