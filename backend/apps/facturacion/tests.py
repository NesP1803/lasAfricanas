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
from apps.facturacion.services.upload_custom_pdf_to_factus import upload_custom_pdf_to_factus
from apps.facturacion.services.consecutivo_service import resolve_numbering_range
from apps.facturacion.services.factus_catalog_lookup import (
    get_municipality_id,
    get_payment_method_code,
    get_unit_measure_id,
)
from apps.facturacion.services.factus_payload_builder import build_invoice_payload
from apps.facturacion.services.support_document_payload_builder import build_support_document_payload
from apps.facturacion.services.exceptions import DescargaFacturaError
from apps.facturacion.services.factus_client import (
    FactusAPIError,
    FactusClient,
    FactusPendingCreditNoteError,
    FactusValidationError,
)
from apps.facturacion.services.credit_note_workflow import sincronizar_nota_credito
from apps.facturacion.services.credit_note_service import build_credit_preview, create_credit_note
from apps.facturacion.services.persistence_safety import (
    normalize_qr_image_value,
    safe_assign_charfield,
    safe_assign_json,
)
from apps.core.models import Impuesto
from apps.inventario.models import Categoria, Producto, Proveedor
from apps.ventas.models import Cliente, DetalleVenta, Venta
from apps.ventas.services.anular_venta import anular_venta
from apps.facturacion.models import RangoNumeracionDIAN
from apps.ventas.serializers import VentaListSerializer


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


class FacturaHybridPdfFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='hybrid', password='1234')
        self.cliente = Cliente.objects.create(
            numero_documento='9001',
            nombre='Cliente Híbrido',
            email='hybrid@example.com',
        )
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
            numero_comprobante='FAC-HYB-1',
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-HYB',
            uuid='UUID-HYB',
            number='FAC-HYB-1',
            reference_code='FAC-HYB-1',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            response_json={'ok': True, 'final_fields': {'public_url': 'https://factus.test/public/FAC-HYB-1'}},
        )

    @patch('apps.facturacion.services.upload_custom_pdf_to_factus.FactusClient.upload_custom_pdf')
    def test_upload_custom_pdf_ok(self, mocked_upload):
        mocked_upload.return_value = {'ok': True}

        result = upload_custom_pdf_to_factus(self.factura)

        self.assertTrue(result)
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.pdf_uploaded_to_factus)
        self.assertIsNotNone(self.factura.pdf_uploaded_at)
        self.assertEqual(self.factura.ultimo_error_pdf, '')
        mocked_upload.assert_called_once()

    @patch('apps.facturacion.services.upload_custom_pdf_to_factus.FactusClient.upload_custom_pdf')
    def test_upload_custom_pdf_error_no_rompe_estado_emitido(self, mocked_upload):
        mocked_upload.side_effect = FactusAPIError('timeout upload')
        estado_original = self.factura.estado_electronico

        result = upload_custom_pdf_to_factus(self.factura)

        self.assertFalse(result)
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado_electronico, estado_original)
        self.assertIn('timeout upload', self.factura.ultimo_error_pdf)

    def test_serializer_venta_exhibe_public_url_estable(self):
        self.factura.public_url = ''
        self.factura.qr_data = 'Verifica aquí https://dian.example/consulta/FAC-HYB-1'
        self.factura.save(update_fields=['public_url', 'qr_data', 'updated_at'])

        payload = VentaListSerializer(instance=self.venta).data
        factura_data = payload['factura_electronica']
        self.assertEqual(
            factura_data['factus_public_url'],
            'https://factus.test/public/FAC-HYB-1',
        )

    def test_serializer_venta_oculta_public_url_si_hay_inconsistencia_documental(self):
        self.factura.codigo_error = 'ERROR_CONCILIACION_DOCUMENTAL'
        self.factura.mensaje_error = 'ERROR_CONCILIACION_DOCUMENTAL: total remoto distinto'
        self.factura.save(update_fields=['codigo_error', 'mensaje_error', 'updated_at'])

        payload = VentaListSerializer(instance=self.venta).data
        factura_data = payload['factura_electronica']
        self.assertEqual(factura_data['factus_public_url'], '')
        self.assertTrue(factura_data['documento_inconsistente'])


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

    @patch('apps.facturacion.views.FactusClient.get_invoice_events')
    def test_eventos_endpoint_por_id(self, mocked_events):
        mocked_events.return_value = {'data': [{'event': 'acuse'}]}
        response = self.client.get(f'/api/facturas-electronicas/{self.factura.id}/eventos/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        mocked_events.assert_called_once_with('FV9999')

    @patch('apps.facturacion.views.FactusClient.get_invoice_email_content')
    def test_correo_contenido_endpoint_por_id(self, mocked_email_content):
        mocked_email_content.return_value = {'subject': 'Factura', 'body': 'Hola'}
        response = self.client.get(f'/api/facturas-electronicas/{self.factura.id}/correo/contenido/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['subject'], 'Factura')
        mocked_email_content.assert_called_once_with('FV9999')

    @patch('apps.facturacion.views.FactusClient.send_invoice_email')
    def test_enviar_correo_factus_endpoint_por_id(self, mocked_send_email):
        mocked_send_email.return_value = {'success': True}
        response = self.client.post(f'/api/facturas-electronicas/{self.factura.id}/enviar-correo/', {'email': 'cliente@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.correo_enviado)
        mocked_send_email.assert_called_once_with('FV9999', email='cliente@example.com')

    @patch('apps.facturacion.views.FactusClient.tacit_acceptance')
    def test_aceptacion_tacita_endpoint_por_id(self, mocked_tacit):
        mocked_tacit.return_value = {'success': True}
        response = self.client.post(f'/api/facturas-electronicas/{self.factura.id}/aceptacion-tacita/')
        self.assertEqual(response.status_code, 200)
        mocked_tacit.assert_called_once_with('FV9999')

    @patch('apps.facturacion.views.FactusClient.delete_invoice')
    def test_eliminar_restringida_para_factura_aceptada(self, mocked_delete):
        response = self.client.post(f'/api/facturas-electronicas/{self.factura.id}/eliminar/')
        self.assertEqual(response.status_code, 409)
        mocked_delete.assert_not_called()


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

    @patch('apps.facturacion.services.facturar_venta.download_xml')
    @patch('apps.facturacion.services.facturar_venta.download_pdf')
    @patch('apps.facturacion.services.facturar_venta.resolve_numbering_range')
    @patch('apps.facturacion.services.facturar_venta.build_invoice_payload')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.create_and_validate_invoice')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.get_invoice')
    def test_facturar_venta_concilia_con_show_si_validate_llega_con_totales_incompletos(
        self,
        mocked_get_invoice,
        mocked_create_validate,
        mocked_build_payload,
        mocked_resolve_range,
        _mocked_pdf,
        _mocked_xml,
    ):
        mocked_build_payload.return_value = {
            'numbering_range_id': 1,
            'customer': {
                'identification': '5555',
                'names': 'Cliente QR Largo',
                'identification_document_id': 3,
            },
            'items': [{'code_reference': 'PR-QR-LARGO', 'quantity': 1}],
            'send_email': False,
        }
        mocked_resolve_range.return_value = RangoNumeracionDIAN(prefijo='FV', factus_range_id=1)
        mocked_create_validate.return_value = {
            'data': {
                'bill': {
                    'status': 'valid',
                    'number': 'FV9001',
                    'reference_code': 'FV9001',
                    'cufe': 'CUFE-9001',
                    'uuid': 'UUID-9001',
                    'xml_url': 'https://example.com/fv9001.xml',
                    'pdf_url': 'https://example.com/fv9001.pdf',
                    'totals': {'total': '10.00', 'tax_amount': '0.00', 'taxable_amount': '10.00'},
                }
            }
        }
        mocked_get_invoice.return_value = {
            'data': {
                'bill': {
                    'status': 'valid',
                    'number': 'FV9001',
                    'reference_code': 'FV9001',
                    'customer': {'identification': '5555'},
                    'items': [{'code_reference': 'PR-QR-LARGO'}],
                    'totals': {'total': '119.00', 'tax_amount': '19.00', 'taxable_amount': '100.00'},
                }
            }
        }

        factura = facturar_venta(self.venta.id, triggered_by=self.user)
        factura.refresh_from_db()
        self.assertEqual(factura.estado_electronico, 'ACEPTADA')
        self.assertEqual(factura.codigo_error, '')

    @patch('apps.facturacion.services.facturar_venta.download_xml')
    @patch('apps.facturacion.services.facturar_venta.download_pdf')
    @patch('apps.facturacion.services.facturar_venta.resolve_numbering_range')
    @patch('apps.facturacion.services.facturar_venta.build_invoice_payload')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.create_and_validate_invoice')
    @patch('apps.facturacion.services.facturar_venta.FactusClient.get_invoice')
    def test_facturar_venta_rechaza_inconsistencia_economica_documental(
        self,
        mocked_get_invoice,
        mocked_create_validate,
        mocked_build_payload,
        mocked_resolve_range,
        _mocked_pdf,
        _mocked_xml,
    ):
        mocked_build_payload.return_value = {
            'numbering_range_id': 1,
            'customer': {
                'identification': '5555',
                'names': 'Cliente QR Largo',
                'identification_document_id': 3,
            },
            'items': [{'code_reference': 'PR-QR-LARGO', 'quantity': 1}],
            'send_email': False,
        }
        mocked_resolve_range.return_value = RangoNumeracionDIAN(prefijo='FV', factus_range_id=1)
        mocked_create_validate.return_value = {
            'data': {
                'bill': {
                    'status': 'valid',
                    'number': 'FV9001',
                    'reference_code': 'FV9001',
                    'cufe': 'CUFE-9001',
                    'uuid': 'UUID-9001',
                    'xml_url': 'https://example.com/fv9001.xml',
                    'pdf_url': 'https://example.com/fv9001.pdf',
                    'totals': {'total': '119.00', 'tax_amount': '19.00', 'taxable_amount': '100.00'},
                }
            }
        }
        mocked_get_invoice.return_value = {
            'data': {
                'bill': {
                    'status': 'valid',
                    'number': 'FV9001',
                    'reference_code': 'FV9001',
                    'customer': {'identification': '5555'},
                    'totals': {'total': '8.40336', 'tax_amount': '1.34', 'taxable_amount': '7.06'},
                    'items': [{'code_reference': 'X'}],
                }
            }
        }

        with self.assertRaises(FactusValidationError):
            facturar_venta(self.venta.id, triggered_by=self.user)
        factura = FacturaElectronica.objects.get(venta=self.venta)
        self.assertEqual(factura.estado_electronico, 'RECHAZADA')
        self.assertEqual(factura.codigo_error, 'ERROR_CONCILIACION_DOCUMENTAL')


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

    def test_listado_facturas_no_expone_public_url_si_inconsistente(self):
        self.factura.codigo_error = 'ERROR_CONCILIACION_DOCUMENTAL'
        self.factura.mensaje_error = 'ERROR_CONCILIACION_DOCUMENTAL: mismatch'
        self.factura.save(update_fields=['codigo_error', 'mensaje_error', 'updated_at'])
        response = self.client.get('/api/facturacion/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['public_url'], '')
        self.assertTrue(response.data[0]['documento_inconsistente'])

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
        response_alias = client.post('/api/factus/rangos/seleccionar-activo/', {'range_id': self.rango.id}, format='json')
        self.assertEqual(response_alias.status_code, 200)

    @patch('apps.facturacion.views.sync_numbering_ranges')
    def test_sync_rangos_requiere_admin(self, mocked_sync):
        mocked_sync.return_value = [self.rango]
        client = APIClient()
        client.force_authenticate(self.vendedor)
        response = client.post('/api/configuracion/dian/rangos/sync/', {}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_list_rangos_alias_factus(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get('/api/factus/rangos/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('ranges', response.data)


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

class NotaCreditoFlujoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='nc-user', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='321', nombre='Cliente NC', email='nc@example.com')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-500',
            cliente=self.cliente,
            vendedor=self.user,
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
        categoria = Categoria.objects.create(nombre='NC Categoria')
        proveedor = Proveedor.objects.create(nombre='NC Proveedor')
        self.producto = Producto.objects.create(
            codigo='NC-PROD',
            nombre='Producto NC',
            precio_costo=Decimal('20'),
            precio_venta=Decimal('100'),
            precio_venta_minimo=Decimal('90'),
            stock=Decimal('4'),
            categoria=categoria,
            proveedor=proveedor,
        )
        self.detalle = DetalleVenta.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal('2'),
            precio_unitario=Decimal('100'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            number='SETP90001',
            reference_code='SETP90001',
            cufe='CUFE-NC-1',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            emitida_en_factus=True,
            response_json={
                'data': {
                    'bill': {'id': 90001, 'numbering_range_id': 1},
                    'customer': {'identification': '321', 'names': 'Cliente NC'},
                }
            },
        )

    def test_preview_bloquea_sobre_acreditacion(self):
        with self.assertRaises(ValidationError):
            build_credit_preview(
                self.factura,
                [{'detalle_venta_original_id': self.detalle.id, 'cantidad_a_acreditar': '3', 'afecta_inventario': False}],
            )

    @patch('apps.facturacion.services.credit_note_service.FactusClient.create_and_validate_credit_note')
    def test_crear_nota_credito_parcial_actualiza_estado_factura(self, mocked_create):
        mocked_create.return_value = {'data': {'credit_note': {'number': 'NC100', 'status': 'accepted', 'cufe': 'NC-CUFE'}}}
        nota = create_credit_note(
            factura=self.factura,
            motivo='Devolución parcial',
            lines=[{'detalle_venta_original_id': self.detalle.id, 'cantidad_a_acreditar': '1', 'afecta_inventario': False}],
            is_total=False,
            user=self.user,
        )
        self.factura.refresh_from_db()
        self.assertEqual(nota.tipo_nota, 'PARCIAL')
        self.assertEqual(self.factura.estado_acreditacion, 'CREDITADA_PARCIAL')

    def test_bloquea_anulacion_directa_si_emitida(self):
        with self.assertRaises(ValidationError):
            anular_venta(self.venta, self.user, motivo='prueba')


class NotaCreditoWorkflowCoverageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='nc-api-user', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.cliente = Cliente.objects.create(numero_documento='909', nombre='Cliente workflow', email='wf@example.com')
        self.venta = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-909',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('300'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('57'),
            total=Decimal('357'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('357'),
            cambio=Decimal('0'),
            estado='COBRADA',
        )
        categoria = Categoria.objects.create(nombre='NC Cov Cat')
        proveedor = Proveedor.objects.create(nombre='NC Cov Prov')
        self.producto1 = Producto.objects.create(
            codigo='NC-COV-1',
            nombre='Producto 1',
            precio_costo=Decimal('10'),
            precio_venta=Decimal('100'),
            precio_venta_minimo=Decimal('90'),
            stock=Decimal('1'),
            categoria=categoria,
            proveedor=proveedor,
        )
        self.producto2 = Producto.objects.create(
            codigo='NC-COV-2',
            nombre='Producto 2',
            precio_costo=Decimal('20'),
            precio_venta=Decimal('100'),
            precio_venta_minimo=Decimal('90'),
            stock=Decimal('1'),
            categoria=categoria,
            proveedor=proveedor,
        )
        self.detalle1 = DetalleVenta.objects.create(
            venta=self.venta,
            producto=self.producto1,
            cantidad=Decimal('2'),
            precio_unitario=Decimal('100'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('200'),
            total=Decimal('238'),
        )
        self.detalle2 = DetalleVenta.objects.create(
            venta=self.venta,
            producto=self.producto2,
            cantidad=Decimal('1'),
            precio_unitario=Decimal('100'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('100'),
            total=Decimal('119'),
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            number='SETP90901',
            reference_code='SETP90901',
            cufe='CUFE-WF-1',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            emitida_en_factus=True,
            response_json={
                'data': {
                    'bill': {'id': 90901, 'numbering_range_id': 1},
                    'customer': {'identification': '909', 'names': 'Cliente workflow'},
                }
            },
        )

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    def test_preview_and_partial_total_and_sync(self, mocked_create):
        mocked_create.return_value = {'data': {'credit_note': {'number': 'NC909', 'status': 'accepted', 'cufe': 'CUFE-NC909'}}}

        preview_resp = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/preview/',
            {'motivo': 'preview', 'lines': [{'detalle_venta_original_id': self.detalle1.id, 'cantidad_a_acreditar': '1'}]},
            format='json',
        )
        self.assertEqual(preview_resp.status_code, 200)
        self.assertEqual(preview_resp.data['total'], '119.00')

        parcial_resp = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/parcial/',
            {
                'motivo': 'parcial',
                'lines': [
                    {
                        'detalle_venta_original_id': self.detalle1.id,
                        'cantidad_a_acreditar': '1',
                        'afecta_inventario': False,
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(parcial_resp.status_code, 201)
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado_acreditacion, 'CREDITADA_PARCIAL')

        mocked_create.return_value = {'data': {'credit_note': {'number': 'NC910', 'status': 'accepted', 'cufe': 'CUFE-NC910'}}}
        total_resp = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/total/',
            {'motivo': 'cerrar saldo'},
            format='json',
        )
        self.assertEqual(total_resp.status_code, 201)
        payload = mocked_create.call_args.args[0]
        self.assertIn('bill_id', payload)
        self.assertIn('customer', payload)
        self.assertTrue(payload.get('items'))
        self.assertIn('unit_measure_id', payload['items'][0])
        self.assertIn('standard_code_id', payload['items'][0])
        self.assertIn('tribute_id', payload['items'][0])
        self.assertIn('is_excluded', payload['items'][0])
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado_acreditacion, 'CREDITADA_TOTAL')

        nota = NotaCreditoElectronica.objects.get(number='NC910')
        with patch('apps.facturacion.services.credit_note_workflow.FactusClient.get_credit_note') as mocked_sync:
            mocked_sync.return_value = {'data': {'credit_note': {'number': 'NC910', 'status': 'accepted'}}}
            sync_resp = self.client.post(f'/api/notas-credito/{nota.id}/sincronizar/', {}, format='json')
        self.assertEqual(sync_resp.status_code, 200)

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    def test_validaciones_rechazos(self, mocked_create):
        mocked_create.return_value = {'data': {'credit_note': {'number': 'NC920', 'status': 'accepted', 'cufe': 'CUFE-NC920'}}}

        excedida = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/parcial/',
            {'motivo': 'bad', 'lines': [{'detalle_venta_original_id': self.detalle1.id, 'cantidad_a_acreditar': '9'}]},
            format='json',
        )
        self.assertEqual(excedida.status_code, 400)

        otra_venta = Venta.objects.create(
            tipo_comprobante='FACTURA', numero_comprobante='FAC-X', cliente=self.cliente, vendedor=self.user,
            subtotal=Decimal('1'), descuento_porcentaje=Decimal('0'), descuento_valor=Decimal('0'), iva=Decimal('0.19'),
            total=Decimal('1.19'), medio_pago='EFECTIVO', efectivo_recibido=Decimal('1.19'), cambio=Decimal('0'), estado='COBRADA',
        )
        detalle_ajeno = DetalleVenta.objects.create(
            venta=otra_venta, producto=self.producto1, cantidad=Decimal('1'), precio_unitario=Decimal('1'), descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'), subtotal=Decimal('1'), total=Decimal('1.19')
        )
        ajena = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/parcial/',
            {'motivo': 'bad', 'lines': [{'detalle_venta_original_id': detalle_ajeno.id, 'cantidad_a_acreditar': '1'}]},
            format='json',
        )
        self.assertEqual(ajena.status_code, 400)

        self.factura.estado_electronico = 'RECHAZADA'
        self.factura.save(update_fields=['estado_electronico'])
        estado_invalido = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/parcial/',
            {'motivo': 'bad', 'lines': [{'detalle_venta_original_id': self.detalle1.id, 'cantidad_a_acreditar': '1'}]},
            format='json',
        )
        self.assertEqual(estado_invalido.status_code, 400)

    def test_error_inesperado_no_se_convierte_400(self):
        with patch('apps.facturacion.views.create_credit_note', side_effect=RuntimeError('boom')):
            resp = self.client.post(
                f'/api/facturacion/facturas/{self.factura.id}/notas-credito/parcial/',
                {'motivo': 'x', 'lines': [{'detalle_venta_original_id': self.detalle1.id, 'cantidad_a_acreditar': '1'}]},
                format='json',
            )
        self.assertEqual(resp.status_code, 500)

    def test_error_factus_retorna_502_en_total(self):
        with patch(
            'apps.facturacion.views.create_credit_note',
            side_effect=FactusAPIError(
                "Factus rechazó la factura. Detalle: {'message': 'The route credit-notes/validate could not be found.'}",
                status_code=404,
                provider_detail="{'message': 'The route credit-notes/validate could not be found.'}",
            ),
        ):
            resp = self.client.post(
                f'/api/facturacion/facturas/{self.factura.id}/notas-credito/total/',
                {'motivo': 'x'},
                format='json',
            )
        self.assertEqual(resp.status_code, 502)

    def test_conflicto_nota_pendiente_en_dian_retorna_409(self):
        with patch(
            'apps.facturacion.views.create_credit_note',
            side_effect=FactusPendingCreditNoteError(
                "Factus reportó una nota crédito pendiente en DIAN.",
                status_code=409,
                provider_detail="{'message': 'Se encontró una nota crédito pendiente por enviar a la DIAN'}",
            ),
        ):
            resp = self.client.post(
                f'/api/facturacion/facturas/{self.factura.id}/notas-credito/total/',
                {'motivo': 'x'},
                format='json',
            )
        self.assertEqual(resp.status_code, 409)

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    def test_409_sin_evidencia_remota_queda_en_conflicto_factus(self, mocked_create, mocked_list):
        mocked_create.side_effect = FactusPendingCreditNoteError(
            "Factus reportó una nota crédito pendiente en DIAN.",
            status_code=409,
            provider_detail="{'message': 'Se encontró una nota crédito pendiente por enviar a la DIAN'}",
        )
        mocked_list.return_value = {'data': []}

        resp = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/total/',
            {'motivo': 'x'},
            format='json',
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['estado_local'], 'CONFLICTO_FACTUS')
        self.assertEqual(resp.data['codigo_error'], 'FACTUS_409_SIN_EVIDENCIA_REMOTA')
        self.assertIn('Sincronizar', resp.data['detail'])

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.get_credit_note')
    def test_sync_404_show_y_sin_listado_queda_conflicto_factus(self, mocked_get, mocked_list):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC1073',
            tipo_nota='TOTAL',
            estado_local='EN_PROCESO',
            estado_electronico='PENDIENTE_REINTENTO',
            status='PENDIENTE_REINTENTO',
            request_json={},
            response_json={},
        )
        mocked_get.side_effect = FactusAPIError('Not found', status_code=404)
        mocked_list.return_value = {'data': []}

        resp = self.client.post(f'/api/notas-credito/{nota.id}/sincronizar/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['estado_local'], 'CONFLICTO_FACTUS')
        self.assertEqual(resp.data['codigo_error'], 'FACTUS_SYNC_SIN_EVIDENCIA')

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.get_credit_note')
    def test_creacion_con_nota_abierta_en_proceso_y_sin_evidencia_retorna_202(self, mocked_get, mocked_list):
        NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC1073',
            tipo_nota='TOTAL',
            estado_local='EN_PROCESO',
            estado_electronico='PENDIENTE_REINTENTO',
            status='PENDIENTE_REINTENTO',
            request_json={},
            response_json={},
        )
        mocked_get.side_effect = FactusAPIError('Not found', status_code=404)
        mocked_list.return_value = {'data': []}

        resp = self.client.post(
            f'/api/facturacion/facturas/{self.factura.id}/notas-credito/total/',
            {'motivo': 'x'},
            format='json',
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['estado_local'], 'CONFLICTO_FACTUS')


class FactusClientCreditNoteFallbackTests(TestCase):
    @patch('apps.facturacion.services.factus_client.FactusClient.send_credit_note')
    def test_retry_credit_note_endpoint_with_v1_when_route_not_found(self, mocked_send):
        client = FactusClient()
        client.credit_note_path = '/credit-notes/validate'
        mocked_send.side_effect = [
            FactusAPIError(
                "Factus rechazó la factura. Detalle: {'message': 'The route credit-notes/validate could not be found.'}",
                status_code=404,
                provider_detail="{'message': 'The route credit-notes/validate could not be found.'}",
            ),
            {'data': {'credit_note': {'number': 'NC-OK'}}},
        ]

        response = client.create_and_validate_credit_note({'items': [{'name': 'x'}]})

        self.assertEqual(response['data']['credit_note']['number'], 'NC-OK')
        self.assertEqual(mocked_send.call_count, 2)


class CreditNoteWorkflowHardeningTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='nc-hard', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='9001', nombre='Cliente NC')
        self.categoria = Categoria.objects.create(nombre='NC CAT')
        self.proveedor = Proveedor.objects.create(nombre='NC PROV')
        self.producto = Producto.objects.create(
            codigo='NC-1',
            nombre='Producto NC',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('10'),
            precio_venta=Decimal('20'),
            precio_venta_minimo=Decimal('15'),
            stock=10,
            stock_minimo=1,
            iva_porcentaje=Decimal('19'),
        )
        self.venta = Venta.objects.create(
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
            estado='FACTURADA',
            inventario_ya_afectado=True,
        )
        self.detalle = DetalleVenta.objects.create(
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal('1'),
            precio_unitario=Decimal('20'),
            descuento_unitario=Decimal('0'),
            iva_porcentaje=Decimal('19'),
            subtotal=Decimal('20'),
            total=Decimal('23.8'),
            afecto_inventario=True,
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-WF',
            uuid='UUID-WF',
            number='FV-WF',
            reference_code='FV-WF',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            emitida_en_factus=True,
            response_json={'data': {'bill': {'id': 99, 'numbering_range_id': 1}}},
        )

    def _lines(self):
        return [{'detalle_venta_original_id': self.detalle.id, 'cantidad_a_acreditar': '1', 'afecta_inventario': True, 'motivo_linea': 'x'}]

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.get_credit_note')
    def test_no_aplica_efectos_si_queda_pendiente_dian(self, mocked_get, mocked_create):
        mocked_create.return_value = {'data': {'credit_note': {'number': 'NC-P1', 'status': 'pending'}}}
        mocked_get.side_effect = FactusAPIError('not found', status_code=404)
        nota, meta = create_credit_note(factura=self.factura, motivo='x', lines=self._lines(), is_total=False, user=self.user)
        self.assertEqual(nota.estado_local, 'PENDIENTE_DIAN')
        self.assertFalse(meta['business_effects_applied'])
        self.assertEqual(MovimientoInventario.objects.filter(tipo='DEVOLUCION').count(), 0)

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    def test_aplica_efectos_si_aceptada(self, mocked_create):
        mocked_create.return_value = {'data': {'credit_note': {'number': 'NC-A1', 'cufe': 'CUFE-NC', 'uuid': 'UUID-NC', 'status': 'accepted'}}}
        nota, meta = create_credit_note(factura=self.factura, motivo='x', lines=self._lines(), is_total=False, user=self.user)
        self.assertEqual(nota.estado_local, 'ACEPTADA')
        self.assertTrue(meta['business_effects_applied'])
        self.assertEqual(MovimientoInventario.objects.filter(tipo='DEVOLUCION').count(), 1)

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    def test_409_reconciliacion_exacta_no_duplica(self, mocked_list, mocked_create):
        mocked_create.side_effect = FactusPendingCreditNoteError('409', status_code=409)
        mocked_list.return_value = {'data': {'credit_notes': [{'number': 'NC-R1', 'reference_code': 'NC-1-PARCIAL', 'bill_number': 'FV-WF', 'status': 'pending'}]}}
        with patch('apps.facturacion.services.credit_note_workflow._build_reference_code', return_value='NC-1-PARCIAL'):
            nota, meta = create_credit_note(factura=self.factura, motivo='x', lines=self._lines(), is_total=False, user=self.user)
        self.assertEqual(NotaCreditoElectronica.objects.filter(factura=self.factura).count(), 1)
        self.assertIn(meta['result'], {'pending_dian', 'accepted'})
        self.assertEqual(nota.number, 'NC-R1')

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    def test_409_sin_evidencia_exacta_queda_pendiente_sin_duplicar(self, mocked_list, mocked_create):
        mocked_create.side_effect = FactusPendingCreditNoteError('409', status_code=409)
        mocked_list.return_value = {'data': {'credit_notes': [{'number': 'NC-OTRA', 'reference_code': 'DIFERENTE', 'bill_number': 'FV-OTRA'}]}}
        with patch('apps.facturacion.services.credit_note_workflow._build_reference_code', return_value='NC-1-PARCIAL'):
            nota, meta = create_credit_note(factura=self.factura, motivo='x', lines=self._lines(), is_total=False, user=self.user)
        self.assertEqual(NotaCreditoElectronica.objects.filter(factura=self.factura).count(), 1)
        self.assertEqual(nota.estado_local, 'PENDIENTE_DIAN')
        self.assertEqual(meta['result'], 'pending_dian')

    def test_refresh_acreditacion_no_cuenta_pendientes(self):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC-PEND',
            tipo_nota='PARCIAL',
            estado_local='PENDIENTE_DIAN',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={},
            response_json={},
        )
        NotaCreditoDetalle.objects.create(
            nota_credito=nota,
            detalle_venta_original=self.detalle,
            producto=self.producto,
            cantidad_original_facturada=Decimal('1'),
            cantidad_ya_acreditada=Decimal('0'),
            cantidad_a_acreditar=Decimal('1'),
            precio_unitario=Decimal('20'),
            descuento=Decimal('0'),
            base_impuesto=Decimal('20'),
            impuesto=Decimal('3.8'),
            total_linea=Decimal('23.8'),
            afecta_inventario=True,
        )
        from apps.facturacion.services.credit_note_workflow import _refresh_invoice_credit_status
        _refresh_invoice_credit_status(self.factura)
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado_acreditacion, 'ACTIVA')

    def test_permite_multiples_parciales_aceptadas(self):
        NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC-H1',
            tipo_nota='PARCIAL',
            estado_local='ACEPTADA',
            estado_electronico='ACEPTADA',
            status='ACEPTADA',
            request_json={},
            response_json={},
        )
        NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC-H2',
            tipo_nota='PARCIAL',
            estado_local='ACEPTADA',
            estado_electronico='ACEPTADA',
            status='ACEPTADA',
            request_json={},
            response_json={},
        )
        self.assertEqual(NotaCreditoElectronica.objects.filter(factura=self.factura, tipo_nota='PARCIAL', estado_local='ACEPTADA').count(), 2)

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.get_credit_note')
    def test_sync_prioriza_reference_code_si_show_number_404(self, mocked_get, mocked_list):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC1073',
            tipo_nota='PARCIAL',
            estado_local='PENDIENTE_DIAN',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={},
            response_json={},
            reference_code='NC-1-PARCIAL',
        )
        mocked_get.side_effect = FactusAPIError('not found', status_code=404)
        mocked_list.return_value = {
            'data': {
                'credit_notes': [
                    {'number': 'NC999', 'reference_code': 'NC-OTRA', 'bill_number': self.factura.number, 'status': 'pending'},
                    {'number': 'NC1073', 'reference_code': 'NC-1-PARCIAL', 'bill_number': self.factura.number, 'status': 'accepted', 'cufe': 'CUFE-NC'},
                ]
            }
        }
        synced = sincronizar_nota_credito(nota.id)
        self.assertEqual(synced.estado_local, 'ACEPTADA')
        self.assertEqual(synced.reference_code, 'NC-1-PARCIAL')
        self.assertEqual(synced.last_remote_error, '')

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    def test_sync_timeout_transitorio_queda_pendiente(self, mocked_list):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='',
            tipo_nota='PARCIAL',
            estado_local='PENDIENTE_ENVIO',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={},
            response_json={},
            reference_code='NC-TIMEOUT',
        )
        mocked_list.side_effect = FactusAPIError('timeout')
        synced = sincronizar_nota_credito(nota.id)
        self.assertEqual(synced.estado_local, 'PENDIENTE_DIAN')
        self.assertEqual(synced.codigo_error, 'FACTUS_TIMEOUT_O_TRANSITORIO')

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.create_and_validate_credit_note')
    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    def test_sync_replay_validate_mismo_reference_code_recupera(self, mocked_list, mocked_replay):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='',
            tipo_nota='PARCIAL',
            estado_local='CONFLICTO_FACTUS',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={'reference_code': 'NC-REPLAY', 'items': [{'name': 'x'}]},
            response_json={},
            reference_code='NC-REPLAY',
        )
        mocked_list.side_effect = FactusAPIError('not-found', status_code=404)
        mocked_replay.return_value = {'data': {'credit_note': {'number': 'NC-REPLAY-1', 'reference_code': 'NC-REPLAY', 'cufe': 'CUFE-REPLAY', 'status': 'accepted'}}}
        synced = sincronizar_nota_credito(nota.id)
        self.assertEqual(synced.estado_local, 'ACEPTADA')
        self.assertEqual(synced.number, 'NC-REPLAY-1')

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    def test_reintento_idempotente_no_duplica(self, mocked_list):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='',
            tipo_nota='PARCIAL',
            estado_local='CONFLICTO_FACTUS',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={},
            response_json={},
            reference_code='NC-IDEMP',
        )
        mocked_list.return_value = {'data': {'credit_notes': [{'number': 'NC-IDEMP-1', 'reference_code': 'NC-IDEMP', 'status': 'pending'}]}}
        first = sincronizar_nota_credito(nota.id)
        second = sincronizar_nota_credito(nota.id)
        self.assertEqual(first.id, second.id)
        self.assertEqual(NotaCreditoElectronica.objects.filter(reference_code='NC-IDEMP').count(), 1)


class CreditNoteEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='nc-endpoint', password='1234')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cliente = Cliente.objects.create(numero_documento='9301', nombre='Cliente Endpoints')
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
            inventario_ya_afectado=True,
        )
        self.factura = FacturaElectronica.objects.create(
            venta=self.venta,
            cufe='CUFE-END',
            uuid='UUID-END',
            number='FV-END',
            reference_code='FV-END',
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            emitida_en_factus=True,
            response_json={'data': {'bill': {'id': 77, 'numbering_range_id': 1}}},
        )
        self.nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            venta_origen=self.venta,
            number='NC-END',
            reference_code='NC-END-RC',
            tipo_nota='PARCIAL',
            estado_local='CONFLICTO_FACTUS',
            estado_electronico='PENDIENTE_DIAN',
            status='PENDIENTE_DIAN',
            request_json={},
            response_json={'data': {'credit_note': {'reference_code': 'NC-END-RC'}}},
            sync_metadata={'attempts': 1},
        )

    def test_estado_remoto_endpoint(self):
        response = self.client.get(f'/api/notas-credito/{self.nota.id}/estado-remoto/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['reference_code'], 'NC-END-RC')
        self.assertIn('remote_response', response.data)

    @patch('apps.facturacion.services.credit_note_workflow.FactusClient.list_credit_notes')
    def test_reintentar_conciliacion_endpoint(self, mocked_list):
        mocked_list.return_value = {'data': {'credit_notes': [{'number': 'NC-END', 'reference_code': 'NC-END-RC', 'status': 'pending'}]}}
        response = self.client.post(f'/api/notas-credito/{self.nota.id}/reintentar-conciliacion/', {}, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertIn(response.data['estado_local'], {'PENDIENTE_DIAN', 'CONFLICTO_FACTUS'})
