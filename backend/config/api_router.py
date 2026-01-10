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

# Importar ViewSets de Taller
from apps.taller.views import (
    MecanicoViewSet,
    ServicioMotoViewSet,
    RepuestoAsignadoViewSet,
    ConsumoRepuestoViewSet
)

# Importar ViewSets de Configuración
from apps.core.views import (
    ConfiguracionEmpresaViewSet,
    ImpuestoViewSet,
    AuditoriaViewSet,
    ConfiguracionFacturacionViewSet,
    UsuarioViewSet,
    BackupViewSet
)

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

# Registrar ViewSets de Taller
router.register(r'mecanicos', MecanicoViewSet, basename='mecanico')
router.register(r'servicios', ServicioMotoViewSet, basename='servicio')
router.register(r'repuestos-asignados', RepuestoAsignadoViewSet, basename='repuesto-asignado')
router.register(r'consumos', ConsumoRepuestoViewSet, basename='consumo')

# Registrar ViewSets de Configuración
router.register(r'config/empresa', ConfiguracionEmpresaViewSet, basename='config-empresa')
router.register(r'config/impuestos', ImpuestoViewSet, basename='config-impuesto')
router.register(r'config/auditoria', AuditoriaViewSet, basename='config-auditoria')
router.register(r'config/facturacion', ConfiguracionFacturacionViewSet, basename='config-facturacion')
router.register(r'config/usuarios', UsuarioViewSet, basename='config-usuario')
router.register(r'config/backup', BackupViewSet, basename='config-backup')