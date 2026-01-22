"""
Router central de la API
Registra todos los ViewSets aquí
"""
from rest_framework.routers import DefaultRouter

# Importar ViewSets
from apps.inventario.views import (
    CategoriaViewSet,
    ProveedorViewSet,
    ProductoViewSet,
    MovimientoInventarioViewSet
)
from apps.ventas.views import (
    ClienteViewSet,
    VentaViewSet
)

from apps.core.views import (
    ConfiguracionEmpresaViewSet,
    ConfiguracionFacturacionViewSet,
    ImpuestoViewSet,
    AuditoriaViewSet,
)
from apps.usuarios.views import UsuarioViewSet
from apps.taller.views import MecanicoViewSet, MotoViewSet, OrdenTallerViewSet


# Crear router único
router = DefaultRouter()

# Registrar ViewSets de Inventario
router.register(r'categorias', CategoriaViewSet, basename='categoria')
router.register(r'proveedores', ProveedorViewSet, basename='proveedor')
router.register(r'productos', ProductoViewSet, basename='producto')
router.register(r'movimientos', MovimientoInventarioViewSet, basename='movimiento')

# Registrar ViewSets de Ventas
router.register(r'clientes', ClienteViewSet, basename='cliente')
router.register(r'ventas', VentaViewSet, basename='venta')


# Registrar Configuración y Auditoría
router.register(r'configuracion-empresa', ConfiguracionEmpresaViewSet, basename='configuracion-empresa')
router.register(r'configuracion-facturacion', ConfiguracionFacturacionViewSet, basename='configuracion-facturacion')
router.register(r'impuestos', ImpuestoViewSet, basename='impuesto')
router.register(r'auditoria', AuditoriaViewSet, basename='auditoria')

# Registrar Usuarios
router.register(r'usuarios', UsuarioViewSet, basename='usuario')

# Registrar Taller
router.register(r'mecanicos', MecanicoViewSet, basename='mecanico')
router.register(r'motos', MotoViewSet, basename='moto')
router.register(r'ordenes-taller', OrdenTallerViewSet, basename='orden-taller')
