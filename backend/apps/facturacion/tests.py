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
from django.db import DataError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.facturacion.models import DocumentoSoporteElectronico, FacturaElectronica, NotaCreditoElectronica
from apps.facturacion_electronica.catalogos.models import DocumentoIdentificacionFactus
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.electronic_state_machine import map_factus_status, resolve_actions
from apps.facturacion.services.facturar_venta import facturar_venta
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.factus_catalog_lookup import (
    get_municipality_id,
    get_payment_method_code,
    get_unit_measure_id,
)
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.support_document_payload_builder import build_support_document_payload
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import FactusValidationError
from apps.facturacion.services.persistence_safety import (
    normalize_qr_image_value,
    safe_assign_charfield,
    safe_assign_json,
)
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


class FacturacionPersistenciaDefensivaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='persist-user', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='789', nombre='Cliente Persistencia')
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

    def test_safe_assign_charfield_trunca_codigo_error_largo(self):
        factura = FacturaElectronica.objects.create(
            venta=self.venta,
            status='ERROR_INTEGRACION',
            estado_electronico='ERROR_INTEGRACION',
            response_json={'ok': False},
        )
        was_truncated = safe_assign_charfield(factura, 'codigo_error', 'X' * 600)
        self.assertTrue(was_truncated)
        self.assertEqual(len(factura.codigo_error), 50)

    def test_safe_assign_json_guarda_payload_grande_sin_charfield(self):
        factura = FacturaElectronica.objects.create(
            venta=self.venta,
            status='PENDIENTE_REINTENTO',
            estado_electronico='PENDIENTE_REINTENTO',
            response_json={'ok': False},
        )
        payload_grande = {'errores': ['E' * 1000], 'observaciones': 'OBS' * 500}
        safe_assign_json(factura, 'response_json', payload_grande)
        factura.save(update_fields=['response_json', 'updated_at'])
        factura.refresh_from_db()
        self.assertIsInstance(factura.response_json, dict)
        self.assertIn('errores', factura.response_json)

    def test_public_url_larga_se_persiste_sin_overflow(self):
        factura = FacturaElectronica.objects.create(
            venta=self.venta,
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            response_json={'ok': True},
        )
        factura.public_url = f'https://example.com/{"a" * 1300}'
        factura.save(update_fields=['public_url', 'updated_at'])
        factura.refresh_from_db()
        self.assertTrue(factura.public_url.endswith('a' * 1300))

    def test_normalize_qr_image_separa_data_url_y_url_remota(self):
        data_url = f'data:image/png;base64,{"A" * 5000}'
        qr_url, qr_data = normalize_qr_image_value(data_url)
        self.assertEqual(qr_url, '')
        self.assertTrue(qr_data.startswith('data:image/png;base64,'))

        remote_url = 'https://factus.test/qr/FV-1001.png'
        qr_url, qr_data = normalize_qr_image_value(remote_url)
        self.assertEqual(qr_url, remote_url)
        self.assertEqual(qr_data, '')


class FacturarVentaPersistenciaCriticaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='persist-critical', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='5555', nombre='Cliente QR Largo')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FV9001',
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
        DetalleVenta.objects.create(
            venta=self.venta,
            producto=Producto.objects.create(
                codigo='PR-QR-LARGO',
                nombre='Producto QR',
                precio_costo=Decimal('50'),
                precio_venta=Decimal('100'),
                precio_venta_minimo=Decimal('100'),
                stock=Decimal('10'),
                categoria=Categoria.objects.create(nombre='General'),
                proveedor=Proveedor.objects.create(nombre='Proveedor QR'),
            ),
            cantidad=1,
            precio_unitario=Decimal('100'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('100'),
            total=Decimal('119'),
        )

    @patch('apps.facturacion.services.facturar_venta.download_xml')
    @patch('apps.facturacion.services.facturar_venta.download_pdf')
    @patch('apps.facturacion.services.facturar_venta.resolve_numbering_range')
    @patch('apps.facturacion.services.facturar_venta.build_invoice_payload')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.send_invoice')
    def test_qr_image_data_url_largo_no_desborda_qr_image_url(
        self,
        mocked_send_invoice,
        mocked_build_payload,
        mocked_resolve_range,
        _mocked_pdf,
        _mocked_xml,
    ):
        mocked_build_payload.return_value = {
            'numbering_range_id': 1,
            'customer': {
                'identification': '900123123',
                'names': 'Cliente QR Largo',
                'identification_document_id': 3,
            },
            'items': [{'code_reference': 'PR-QR-LARGO', 'quantity': 1}],
            'send_email': False,
        }
        mocked_resolve_range.return_value = RangoNumeracionDIAN(prefijo='FV', factus_range_id=1)
        mocked_send_invoice.return_value = {
            'data': {
                'bill': {
                    'status': 'valid',
                    'number': 'FV9001',
                    'reference_code': 'FV9001',
                    'cufe': 'CUFE-9001',
                    'uuid': 'UUID-9001',
                    'xml_url': 'https://example.com/fv9001.xml',
                    'pdf_url': 'https://example.com/fv9001.pdf',
                    'qr_image': f'data:image/png;base64,{"A" * 13079}',
                }
            }
        }

        factura = facturar_venta(self.venta.id, triggered_by=self.user)
        factura.refresh_from_db()
        self.assertEqual(factura.estado_electronico, 'ACEPTADA')
        self.assertEqual(factura.qr_image_url, '')
        self.assertTrue(factura.qr_image_data.startswith('data:image/png;base64,'))


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

    def test_normaliza_tipo_documento_proveedor_cc_y_homologa_id(self):
        payload = build_support_document_payload(
            {
                'proveedor_nombre': 'Juan Perez',
                'proveedor_documento': '123',
                'proveedor_tipo_documento': ' c.c ',
                'payment_method_code': '10',
                'items': [{'descripcion': 'Servicio', 'cantidad': 1, 'precio': 15000}],
            }
        )
        self.assertEqual(payload['supplier']['identification_type'], 'CC')
        self.assertEqual(payload['supplier']['identification_document_id'], 3)


class FactusCatalogLookupHomologationTests(TestCase):
    def test_lookup_prioriza_homologaciones_locales(self):
        from apps.facturacion_electronica.models import (
            HomologacionMedioPago,
            HomologacionMunicipio,
            HomologacionUnidadMedida,
        )

        HomologacionMunicipio.objects.create(codigo_interno='BOGOTA DC', municipality_id=321)
        HomologacionUnidadMedida.objects.create(codigo_interno='UN', unit_measure_id=70)
        HomologacionMedioPago.objects.create(codigo_interno='EFECTIVO', payment_method_code='10')

        self.assertEqual(get_municipality_id('Bogotá D.C.', default=0), 321)
        self.assertEqual(get_unit_measure_id('un', default=0), 70)
        self.assertEqual(get_payment_method_code('efectivo', default=''), '10')


class SyncFactusCatalogsCommandTests(TestCase):
    def test_skip_remote_ensure_minimums_carga_catalogos_base(self):
        out = StringIO()
        call_command('sync_factus_catalogs', '--skip-remote', stdout=out)
        self.assertTrue(
            DocumentoIdentificacionFactus.objects.filter(factus_id=3, codigo='13', is_active=True).exists()
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
    def test_payload_gravado_envia_precio_base_unitario(
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
    def test_payload_producto_0365_envia_precio_base_504_20(
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


class FactusCustomerDocumentHomologationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='payload-doc', password='1234')
        self.cliente = Cliente.objects.create(
            numero_documento='123456789',
            nombre='Cliente Homologación',
            tipo_documento='CC',
        )
        self.categoria = Categoria.objects.create(nombre='Factus Doc')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor Doc')
        self.producto = Producto.objects.create(
            codigo='FD-001',
            nombre='Producto Doc',
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
        Impuesto.objects.create(
            nombre='IVA 19',
            porcentaje=Decimal('19.00'),
            factus_tribute_id=1,
            is_active=True,
        )

    def _crear_venta(self):
        venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-910000',
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
            producto=self.producto,
            cantidad=Decimal('1.00'),
            precio_unitario=Decimal('3000.00'),
            descuento_unitario=Decimal('0.00'),
            iva_porcentaje=Decimal('19.00'),
            subtotal=Decimal('2521.01'),
            total=Decimal('3000.00'),
        )
        return venta

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_homologa_cc_en_minuscula_y_espacios_a_codigo_factus(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        DocumentoIdentificacionFactus.objects.create(factus_id=3, codigo='13', nombre='CC', is_active=True)
        self.cliente.tipo_documento = ' cc '
        self.cliente.save(update_fields=['tipo_documento'])
        venta = self._crear_venta()
        payload = build_invoice_payload(venta)
        self.assertEqual(payload['customer']['identification_document_id'], 3)

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_lanza_error_claro_si_tipo_documento_no_homologado(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        self.cliente.tipo_documento = 'RUTX'
        self.cliente.save(update_fields=['tipo_documento'])
        venta = self._crear_venta()
        with self.assertRaises(FactusValidationError) as exc:
            build_invoice_payload(venta)
        self.assertIn("El tipo de documento 'RUTX' no está homologado para Factus.", str(exc.exception))

    @patch('apps.facturacion.services.factus_payload_builder.get_tribute_id', return_value=1)
    @patch('apps.facturacion.services.factus_payload_builder.get_municipality_id', return_value=149)
    @patch('apps.facturacion.services.factus_payload_builder.get_payment_method_code', return_value='10')
    @patch('apps.facturacion.services.factus_payload_builder.get_unit_measure_id', return_value=70)
    @patch('apps.facturacion.services.factus_payload_builder.resolve_numbering_range')
    def test_rechaza_cliente_general_sin_datos_fiscales_validos(
        self,
        mocked_range,
        _mocked_um,
        _mocked_payment,
        _mocked_municipality,
        _mocked_tribute,
    ):
        mocked_range.return_value = MagicMock(factus_range_id=99)
        self.cliente.nombre = 'Cliente General'
        self.cliente.numero_documento = '222222222222'
        self.cliente.tipo_documento = 'CC'
        self.cliente.save(update_fields=['nombre', 'numero_documento', 'tipo_documento'])
        venta = self._crear_venta()
        with self.assertRaises(FactusValidationError) as exc:
            build_invoice_payload(venta)
        self.assertIn(
            'El cliente general no puede usarse para facturación electrónica sin identificación fiscal válida.',
            str(exc.exception),
        )

class ElectronicStateMachineTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='fsm-user', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='999', nombre='Cliente FSM')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FVFSM1',
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

    def test_estado_aceptada(self):
        estado, raw = map_factus_status({'data': {'bill': {'status': 'valid', 'number': 'FV1', 'cufe': 'CUFE1'}}})
        self.assertEqual(estado, 'ACEPTADA')
        self.assertEqual(raw, 'valid')

    def test_estado_aceptada_con_observaciones(self):
        estado, _ = map_factus_status(
            {'data': {'bill': {'status': 'valid', 'number': 'FV1', 'cufe': 'CUFE1', 'errors': ['Obs']}}}
        )
        self.assertEqual(estado, 'ACEPTADA_CON_OBSERVACIONES')

    def test_estado_rechazada_por_validacion(self):
        estado, _ = map_factus_status({'data': {'bill': {'status': 'rejected', 'errors': ['campo inválido']}}})
        self.assertEqual(estado, 'RECHAZADA')

    def test_estado_pendiente_reintento(self):
        estado, _ = map_factus_status({'data': {'bill': {'status': 'pending'}}})
        self.assertEqual(estado, 'PENDIENTE_REINTENTO')

    def test_acciones_error_integracion(self):
        self.assertIn('reintentar_emision', resolve_actions('ERROR_INTEGRACION'))

    def test_acciones_error_persistencia(self):
        acciones = resolve_actions('ERROR_PERSISTENCIA')
        self.assertIn('sincronizar_factus', acciones)
        self.assertIn('reparar_persistencia', acciones)

    @patch('apps.facturacion.services.facturar_venta.download_xml')
    @patch('apps.facturacion.services.facturar_venta.download_pdf')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.send_invoice')
    def test_no_duplicacion_al_reintentar(self, mocked_send_invoice, _mocked_pdf, _mocked_xml):
        FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-EXISTENTE',
            uuid='UUID-EXISTENTE',
            number='FVFSM1',
            reference_code='FVFSM1',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            response_json={'ok': True},
        )
        factura = facturar_venta(self.venta.id, triggered_by=self.user)
        self.assertEqual(factura.estado_electronico, 'ACEPTADA')
        mocked_send_invoice.assert_not_called()


class FacturarVentaPersistenciaQrTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='qr-user', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='777', nombre='Cliente QR', tipo_documento='CC')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC9001',
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

    def test_normalize_qr_image_data_url(self):
        url, data = normalize_qr_image_value('data:image/png;base64,' + ('A' * 100))
        self.assertEqual(url, '')
        self.assertTrue(data.startswith('data:image/png;base64,'))

    @patch('apps.facturacion.services.facturar_venta.download_xml')
    @patch('apps.facturacion.services.facturar_venta.download_pdf')
    @patch('apps.facturacion.services.facturar_venta.resolve_numbering_range')
    @patch('apps.facturacion.services.facturar_venta.build_invoice_payload')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.send_invoice')
    def test_facturar_venta_mueve_qr_base64_a_textfield_sin_overflow(
        self,
        mocked_send_invoice,
        mocked_build_payload,
        mocked_resolve_range,
        _mocked_pdf,
        _mocked_xml,
    ):
        mocked_resolve_range.return_value = MagicMock(prefijo='FAC', factus_range_id=55)
        mocked_build_payload.return_value = {
            'customer': {'identification': '777', 'names': 'Cliente QR', 'identification_document_id': 3},
            'items': [{'sku': 'P1'}],
            'numbering_range_id': 55,
        }
        mocked_send_invoice.return_value = {
            'data': {
                'bill': {
                    'status': 'valid',
                    'number': 'FAC9001',
                    'reference_code': 'FAC9001',
                    'uuid': 'UUID-QR-1',
                    'cufe': 'CUFE-QR-1',
                    'xml_url': 'https://factus.test/xml/FAC9001',
                    'pdf_url': 'https://factus.test/pdf/FAC9001',
                    'qr_image': 'data:image/png;base64,' + ('A' * 14000),
                }
            }
        }
        factura = facturar_venta(self.venta.id, triggered_by=self.user)
        self.assertEqual(factura.estado_electronico, 'ACEPTADA')
        self.assertEqual(factura.qr_image_url, '')
        self.assertTrue((factura.qr_image_data or '').startswith('data:image/png;base64,'))
        self.assertGreater(len(factura.qr_image_data or ''), 2048)

    @patch('apps.facturacion.services.facturar_venta.download_xml')
    @patch('apps.facturacion.services.facturar_venta.download_pdf')
    @patch('apps.facturacion.services.facturar_venta.resolve_numbering_range')
    @patch('apps.facturacion.services.facturar_venta.build_invoice_payload')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.send_invoice')
    @patch('apps.facturacion.services.facturar_venta.FacturaElectronica.save')
    def test_dataerror_no_deja_transaccion_rota_y_marca_error_persistencia(
        self,
        mocked_save,
        mocked_send_invoice,
        mocked_build_payload,
        mocked_resolve_range,
        _mocked_pdf,
        _mocked_xml,
    ):
        mocked_resolve_range.return_value = MagicMock(prefijo='FAC', factus_range_id=55)
        mocked_build_payload.return_value = {
            'customer': {'identification': '777', 'names': 'Cliente QR', 'identification_document_id': 3},
            'items': [{'sku': 'P1'}],
            'numbering_range_id': 55,
        }
        mocked_send_invoice.return_value = {
            'data': {'bill': {'status': 'valid', 'number': 'FAC9001', 'reference_code': 'FAC9001', 'uuid': 'UUID-QR-2', 'cufe': 'CUFE-QR-2', 'xml_url': 'https://factus.test/xml/FAC9001', 'pdf_url': 'https://factus.test/pdf/FAC9001'}}
        }
        real_save = FacturaElectronica.save
        calls = {'n': 0}

        def flaky_save(instance, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] == 1:
                raise DataError('value too long')
            return real_save(instance, *args, **kwargs)

        mocked_save.side_effect = flaky_save
        with self.assertRaises(DataError):
            facturar_venta(self.venta.id, triggered_by=self.user)
        factura = FacturaElectronica.objects.get(venta=self.venta)
        self.assertEqual(factura.estado_electronico, 'ERROR_PERSISTENCIA')
