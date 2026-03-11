from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.facturacion.models import FacturaElectronica
from apps.facturacion.services.download_invoice_files import download_pdf, download_xml
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.ventas.models import Cliente, Venta


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

    def test_xml_endpoint(self):
        response = self.client.get('/api/facturacion/FV9999/xml/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['numero'], 'FV9999')
        self.assertEqual(response.data['xml'], 'facturas/xml/FV9999.xml')

    def test_pdf_endpoint(self):
        response = self.client.get('/api/facturacion/FV9999/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['numero'], 'FV9999')
        self.assertEqual(response.data['pdf'], 'facturas/pdf/FV9999.pdf')


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
