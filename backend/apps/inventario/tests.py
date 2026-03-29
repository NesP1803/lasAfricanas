from decimal import Decimal

from django.test import TestCase

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
