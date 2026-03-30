from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.inventario.models import Categoria, MovimientoInventario, Producto, Proveedor
from apps.usuarios.models import Usuario


class MovimientoInventarioSignalTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='inventario_user',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.categoria = Categoria.objects.create(nombre='Inventario test')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor test')
        self.producto = Producto.objects.create(
            codigo='INV-001',
            nombre='Producto inventario',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('100'),
            precio_venta=Decimal('150'),
            precio_venta_minimo=Decimal('120'),
            stock=Decimal('10'),
            stock_minimo=Decimal('1'),
            iva_porcentaje=Decimal('19'),
        )

    def test_crear_movimiento_sincroniza_stock_persistido_en_producto(self):
        MovimientoInventario.objects.create(
            producto=self.producto,
            tipo='SALIDA',
            cantidad=Decimal('-2'),
            stock_anterior=Decimal('10'),
            stock_nuevo=Decimal('8'),
            costo_unitario=Decimal('100'),
            usuario=self.usuario,
            referencia='TEST-INV-001',
            observaciones='Prueba de signal',
        )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, Decimal('8'))


class ProductoUltimaCompraTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='ultima_compra_user',
            password='pass1234',
            tipo_usuario='VENDEDOR',
        )
        self.categoria = Categoria.objects.create(nombre='Categoría última compra')
        self.proveedor = Proveedor.objects.create(nombre='Proveedor última compra')

    def _crear_producto(self, codigo='INV-ULT-001'):
        return Producto.objects.create(
            codigo=codigo,
            nombre='Producto última compra',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_costo=Decimal('100'),
            precio_venta=Decimal('150'),
            precio_venta_minimo=Decimal('120'),
            stock=Decimal('10'),
            stock_minimo=Decimal('1'),
            iva_porcentaje=Decimal('19'),
        )

    def test_crear_producto_asigna_ultima_compra(self):
        producto = self._crear_producto()
        self.assertIsNotNone(producto.ultima_compra)

    def test_editar_solo_nombre_no_cambia_ultima_compra(self):
        producto = self._crear_producto(codigo='INV-ULT-002')
        ultima_compra_inicial = producto.ultima_compra

        producto.nombre = 'Nombre actualizado'
        producto.save(update_fields=['nombre', 'updated_at'])
        producto.refresh_from_db()

        self.assertEqual(producto.ultima_compra, ultima_compra_inicial)

    def test_editar_stock_cambia_ultima_compra(self):
        producto = self._crear_producto(codigo='INV-ULT-003')
        producto.ultima_compra = timezone.now() - timedelta(days=2)
        producto.save(update_fields=['ultima_compra', 'updated_at'])
        producto.refresh_from_db()
        ultima_compra_inicial = producto.ultima_compra

        producto.stock = Decimal('12')
        producto.save(update_fields=['stock', 'updated_at'])
        producto.refresh_from_db()

        self.assertGreater(producto.ultima_compra, ultima_compra_inicial)

    def test_editar_precio_venta_cambia_ultima_compra(self):
        producto = self._crear_producto(codigo='INV-ULT-004')
        producto.ultima_compra = timezone.now() - timedelta(days=2)
        producto.save(update_fields=['ultima_compra', 'updated_at'])
        producto.refresh_from_db()
        ultima_compra_inicial = producto.ultima_compra

        producto.precio_venta = Decimal('180')
        producto.save(update_fields=['precio_venta', 'updated_at'])
        producto.refresh_from_db()

        self.assertGreater(producto.ultima_compra, ultima_compra_inicial)

    def test_movimiento_salida_cambia_stock_pero_no_ultima_compra(self):
        producto = self._crear_producto(codigo='INV-ULT-005')
        producto.ultima_compra = timezone.now() - timedelta(days=1)
        producto.save(update_fields=['ultima_compra', 'updated_at'])
        producto.refresh_from_db()
        ultima_compra_inicial = producto.ultima_compra

        MovimientoInventario.objects.create(
            producto=producto,
            tipo='SALIDA',
            cantidad=Decimal('-2'),
            stock_anterior=Decimal('10'),
            stock_nuevo=Decimal('8'),
            costo_unitario=Decimal('100'),
            usuario=self.usuario,
            referencia='TEST-ULT-SALIDA',
            observaciones='Prueba SALIDA',
        )

        producto.refresh_from_db()
        self.assertEqual(producto.stock, Decimal('8'))
        self.assertEqual(producto.ultima_compra, ultima_compra_inicial)

    def test_movimiento_devolucion_cambia_stock_pero_no_ultima_compra(self):
        producto = self._crear_producto(codigo='INV-ULT-006')
        producto.ultima_compra = timezone.now() - timedelta(days=1)
        producto.save(update_fields=['ultima_compra', 'updated_at'])
        producto.refresh_from_db()
        ultima_compra_inicial = producto.ultima_compra

        MovimientoInventario.objects.create(
            producto=producto,
            tipo='DEVOLUCION',
            cantidad=Decimal('2'),
            stock_anterior=Decimal('10'),
            stock_nuevo=Decimal('12'),
            costo_unitario=Decimal('100'),
            usuario=self.usuario,
            referencia='TEST-ULT-DEV',
            observaciones='Prueba DEVOLUCION',
        )

        producto.refresh_from_db()
        self.assertEqual(producto.stock, Decimal('12'))
        self.assertEqual(producto.ultima_compra, ultima_compra_inicial)
