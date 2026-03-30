from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Auditoria
from apps.facturacion.models import FacturaElectronica, NotaCreditoElectronica
from apps.ventas.models import Cliente, Venta


class AuditoriaMiddlewareCrudTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='auditor', password='1234', tipo_usuario='ADMIN', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_registra_create_update_delete(self):
        create_response = self.client.post('/api/categorias/', {'nombre': 'Aud Cat'}, format='json')
        self.assertEqual(create_response.status_code, 201)
        categoria_id = create_response.data['id']

        update_response = self.client.patch(f'/api/categorias/{categoria_id}/', {'nombre': 'Aud Cat 2'}, format='json')
        self.assertEqual(update_response.status_code, 200)

        delete_response = self.client.delete(f'/api/categorias/{categoria_id}/')
        self.assertEqual(delete_response.status_code, 204)

        acciones = list(Auditoria.objects.values_list('accion', flat=True)[:3])
        self.assertCountEqual(acciones, ['CREAR', 'ACTUALIZAR', 'ELIMINAR'])


class AuditoriaFacturacionNotasCreditoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='aud-fact', password='1234', tipo_usuario='ADMIN', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.cliente = Cliente.objects.create(numero_documento='A-1', nombre='Cliente Auditoria FE')
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
            cufe='CUFE-AUD',
            uuid='UUID-AUD',
            number='FV-AUD',
            reference_code='FV-AUD',
            status='ACEPTADA',
            xml_url='https://example.com/aud.xml',
            pdf_url='https://example.com/aud.pdf',
            response_json={'ok': True},
        )

    @patch('apps.facturacion.views.emitir_nota_credito')
    def test_endpoint_facturacion_nota_credito_registra_auditoria(self, mocked_emitir):
        mocked_emitir.return_value = MagicMock(number='NC-FE-1', cufe='CUFE-NC', status='ACEPTADA')

        response = self.client.post(
            f'/api/facturacion/{self.factura.id}/nota-credito/',
            {'motivo': 'Ajuste', 'items': [{'descripcion': 'x', 'cantidad': 1, 'precio': 1000}]},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

        audit = Auditoria.objects.first()
        self.assertEqual(audit.accion, 'CREAR')
        self.assertIn('factura electrónica', audit.notas.lower())

    @patch('apps.facturacion.views.emitir_nota_credito')
    def test_endpoint_notas_credito_create_registra_auditoria(self, mocked_emitir):
        nota = NotaCreditoElectronica.objects.create(
            factura=self.factura,
            number='NC-AUD-1',
            uuid='UUID-NC-AUD',
            cufe='CUFE-NC-AUD',
            status='ACEPTADA',
            xml_url='https://example.com/nc.xml',
            pdf_url='https://example.com/nc.pdf',
            response_json={},
        )
        mocked_emitir.return_value = nota

        response = self.client.post(
            '/api/notas-credito/',
            {
                'factura_id': self.factura.id,
                'motivo': 'Devolución',
                'items': [{'descripcion': 'x', 'cantidad': 1, 'precio': 1000}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)

        audit = Auditoria.objects.first()
        self.assertEqual(audit.accion, 'CREAR')
        self.assertIn('nota crédito electrónica', audit.notas.lower())
