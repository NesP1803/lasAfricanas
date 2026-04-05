from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.services.legacy_excel_importer import Dataset, FileReport, LegacyExcelImporter, to_decimal, to_dt
from apps.inventario.models import Categoria, Producto
from apps.core.models import Auditoria, ConfiguracionFacturacion
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


class LegacyExcelImporterNormalizationTests(TestCase):
    def setUp(self):
        self.importer = LegacyExcelImporter(base_path=None, commit=False, cleanup_temp_on_success=False)
        self.categoria = Categoria.objects.create(nombre='General', descripcion='', orden=0)

    def test_to_decimal_formats(self):
        self.assertEqual(to_decimal("19"), Decimal("19"))
        self.assertEqual(to_decimal("19%"), Decimal("19"))
        self.assertEqual(to_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(to_decimal("1234,56"), Decimal("1234.56"))
        self.assertEqual(to_decimal("1234.56"), Decimal("1234.56"))

    def test_to_decimal_bool_returns_default_without_exception(self):
        self.assertEqual(to_decimal(True, Decimal("7")), Decimal("7"))
        self.assertEqual(to_decimal(False, Decimal("9")), Decimal("9"))

    def test_to_dt_string_and_excel_serial_are_aware(self):
        string_dt = to_dt("2025-01-10 15:30:00")
        serial_dt = to_dt(45200)
        self.assertTrue(timezone.is_aware(string_dt))
        self.assertTrue(timezone.is_aware(serial_dt))

    def test_import_productos_with_iva_zero_and_nineteen(self):
        dataset = Dataset(
            path=Path("dbo_articulos.xlsx"),
            sheet="Sheet1",
            headers=["codigo", "nombre", "categoria", "precio_venta", "costo", "stock", "iva"],
            raw_headers=["codigo", "nombre", "categoria", "precio_venta", "costo", "stock", "iva"],
            rows=[
                {"codigo": "P-001", "nombre": "Prod 1", "categoria": "General", "precio_venta": "100", "costo": "50", "stock": "2", "iva": "0", "_row_number": 2},
                {"codigo": "P-002", "nombre": "Prod 2", "categoria": "General", "precio_venta": "120", "costo": "70", "stock": "4", "iva": "19", "_row_number": 3},
            ],
        )
        report = FileReport(filename="dbo_articulos.xlsx", sheet="Sheet1", classification="productos")
        self.importer._import_productos(dataset, report)

        p1 = Producto.objects.get(codigo="P-001")
        p2 = Producto.objects.get(codigo="P-002")
        self.assertEqual(p1.iva_porcentaje, Decimal("0"))
        self.assertTrue(p1.iva_exento)
        self.assertEqual(p2.iva_porcentaje, Decimal("19"))

    def test_import_productos_handles_true_iva_without_conversionsyntax(self):
        dataset = Dataset(
            path=Path("dbo_articulos.xlsx"),
            sheet="Sheet1",
            headers=["codigo", "nombre", "categoria", "precio_venta", "costo", "stock", "iva"],
            raw_headers=["codigo", "nombre", "categoria", "precio_venta", "costo", "stock", "iva"],
            rows=[
                {"codigo": "P-003", "nombre": "Prod Bool", "categoria": "General", "precio_venta": "100", "costo": "50", "stock": "1", "iva": True, "_row_number": 2},
            ],
        )
        report = FileReport(filename="dbo_articulos.xlsx", sheet="Sheet1", classification="productos")
        self.importer._import_productos(dataset, report)
        p = Producto.objects.get(codigo="P-003")
        self.assertEqual(p.iva_porcentaje, Decimal("19"))


class ConfiguracionFacturacionHistoricoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='cfg-historico', password='1234')
        self.cliente = Cliente.objects.create(numero_documento='CF-1', nombre='Cliente Config Hist')
        self.venta_factura = Venta.objects.create(
            tipo_comprobante='FACTURA',
            numero_comprobante='FAC-1',
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
            factura_electronica_uuid='UUID-HIST-1',
            factura_electronica_cufe='CUFE-HIST-1',
        )
        self.venta_remision = Venta.objects.create(
            tipo_comprobante='REMISION',
            numero_comprobante='REM-1',
            cliente=self.cliente,
            vendedor=self.user,
            subtotal=Decimal('10'),
            descuento_porcentaje=Decimal('0'),
            descuento_valor=Decimal('0'),
            iva=Decimal('0'),
            total=Decimal('10'),
            medio_pago='EFECTIVO',
            efectivo_recibido=Decimal('10'),
            cambio=Decimal('0'),
            estado='COBRADA',
        )
        self.factura_electronica = FacturaElectronica.objects.create(
            venta=self.venta_factura,
            status='ACEPTADA',
            estado_electronico='ACEPTADA',
            number='SETP99001',
            reference_code='REF-SETP99001',
            uuid='UUID-HIST-1',
            cufe='CUFE-HIST-1',
            response_json={'ok': True},
        )

    def test_actualizar_fac_rem_local_solo_afecta_configuracion(self):
        cfg = ConfiguracionFacturacion.objects.create(
            prefijo_factura='FAC',
            numero_factura=1,
            prefijo_remision='REM',
            numero_remision=1,
        )
        cfg.prefijo_factura = 'FACX'
        cfg.numero_factura = 200
        cfg.prefijo_remision = 'RMX'
        cfg.numero_remision = 900
        cfg.save(update_fields=['prefijo_factura', 'numero_factura', 'prefijo_remision', 'numero_remision'])

        self.venta_factura.refresh_from_db()
        self.venta_remision.refresh_from_db()
        self.factura_electronica.refresh_from_db()
        self.assertEqual(self.venta_factura.numero_comprobante, 'FAC-1')
        self.assertEqual(self.venta_remision.numero_comprobante, 'REM-1')
        self.assertEqual(self.factura_electronica.number, 'SETP99001')
        self.assertEqual(self.factura_electronica.uuid, 'UUID-HIST-1')
        self.assertEqual(self.factura_electronica.cufe, 'CUFE-HIST-1')
        self.assertEqual(self.venta_factura.factura_electronica_uuid, 'UUID-HIST-1')
        self.assertEqual(self.venta_factura.factura_electronica_cufe, 'CUFE-HIST-1')
