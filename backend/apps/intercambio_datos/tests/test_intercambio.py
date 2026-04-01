from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.intercambio_datos.models import ImportProfile, ExportProfile
from apps.intercambio_datos.services.analyzers.sheet_classifier import classify_sheet
from apps.intercambio_datos.services.importers import clientes_importer, productos_importer, mecanicos_importer, ventas_importer, detalles_importer
from apps.intercambio_datos.services.rules.tax_rules import parse_tax_value
from apps.intercambio_datos.services.exporters.template_exporter import build_template
from apps.intercambio_datos.services.exporters.data_exporter import export_profile
from apps.ventas.models import Cliente, Venta, DetalleVenta
from apps.inventario.models import Categoria, Producto


class SheetClassifierTests(TestCase):
    def test_detecta_entidad_por_headers(self):
        entity, confidence, _ = classify_sheet('clientes', ['numero_documento', 'nombre', 'telefono'])
        self.assertEqual(entity, 'clientes')
        self.assertGreater(confidence, 20)


class TaxRulesTests(TestCase):
    def test_tax_19_0_exento(self):
        p19, _ = parse_tax_value('19%')
        p0, _ = parse_tax_value('0')
        pex, _ = parse_tax_value('EXENTO')
        self.assertEqual(str(p19['iva_porcentaje']), '19.00')
        self.assertEqual(str(p0['iva_porcentaje']), '0.00')
        self.assertTrue(pex['iva_exento'])


class ImportersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='admin', password='x', tipo_usuario='ADMIN')
        self.profile = ImportProfile.objects.create(nombre='default', codigo='default')
        self.cat = Categoria.objects.create(nombre='General')

    def test_importacion_clientes_idempotente(self):
        payload = {'numero_documento': '123', 'nombre': 'Cliente Uno'}
        action1, _, _ = clientes_importer.import_row(payload)
        action2, _, _ = clientes_importer.import_row(payload)
        self.assertEqual(action1, 'INSERTADA')
        self.assertEqual(action2, 'ACTUALIZADA')
        self.assertEqual(Cliente.objects.filter(numero_documento='123').count(), 1)

    def test_importacion_productos(self):
        action, _, _ = productos_importer.import_row({
            'codigo': 'P1', 'nombre': 'Prod 1', 'categoria': 'General', 'precio_venta': '10000', 'precio_costo': '5000', 'impuesto': '19%'
        })
        self.assertIn(action, ['INSERTADA', 'ACTUALIZADA'])
        self.assertTrue(Producto.objects.filter(codigo='P1').exists())

    def test_empleados_no_son_mecanicos(self):
        action, _, _ = mecanicos_importer.import_row({'nombre': 'Juan', 'tipo_usuario': 'empleado'})
        self.assertEqual(action, 'AMBIGUA')

    def test_prevencion_detalles_huerfanos(self):
        action, _, msg = detalles_importer.import_row({'venta_numero': 'V-1', 'producto_codigo': 'P-1'})
        self.assertEqual(action, 'ERROR')
        self.assertIn('huérfano', msg)

    def test_import_ventas_detalles(self):
        clientes_importer.import_row({'numero_documento': '999', 'nombre': 'Cliente Venta'})
        productos_importer.import_row({'codigo': 'P2', 'nombre': 'Prod 2', 'categoria': 'General', 'precio_venta': '2000', 'precio_costo': '1000', 'impuesto': '0%'})
        action, venta, _ = ventas_importer.import_row({'numero_comprobante': 'FAC-1', 'cliente_documento': '999', 'subtotal': '1000', 'iva': '190', 'total': '1190', 'medio_pago': 'EFECTIVO'}, self.user)
        self.assertIn(action, ['INSERTADA', 'ACTUALIZADA'])
        d_action, _, _ = detalles_importer.import_row({'venta_numero': 'FAC-1', 'producto_codigo': 'P2', 'cantidad': '1', 'precio_unitario': '1000', 'iva_porcentaje': '19'})
        self.assertIn(d_action, ['INSERTADA', 'ACTUALIZADA'])
        self.assertEqual(Venta.objects.filter(numero_comprobante='FAC-1').count(), 1)
        self.assertEqual(DetalleVenta.objects.filter(venta=venta).count(), 1)


class ExportTests(TestCase):
    def setUp(self):
        ExportProfile.objects.create(nombre='Full', codigo='full', entidades=['all'])

    def test_exportacion_plantilla(self):
        payload = build_template('clientes')
        self.assertGreater(len(payload), 50)

    def test_exportacion_datos(self):
        payload = export_profile('full')
        self.assertGreater(len(payload), 50)
