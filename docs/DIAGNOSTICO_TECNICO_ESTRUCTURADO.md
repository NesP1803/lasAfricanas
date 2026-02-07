# Diagnóstico técnico estructurado (estado actual)

## 1) Mapa del sistema (resumen factual)

### Backend (Django + DRF)
- **Inventario (`apps/inventario`)**: gestiona categorías, proveedores, productos, movimientos de inventario y favoritos por usuario. Incluye acciones para búsqueda por código, stock bajo, estadísticas y ajuste manual de stock.  
- **Ventas/Caja (`apps/ventas`)**: gestiona clientes, ventas (cotización/remisión/factura), flujo de envío a caja, facturación en caja, conversión remisión→factura, anulación y solicitudes de descuento.  
- **Taller (`apps/taller`)**: gestiona mecánicos, motos y órdenes de taller; permite agregar/quitar repuestos y facturar orden generando venta.  
- **Usuarios (`apps/usuarios`)**: administra usuarios, cambio de contraseña, perfil actual (`me`), validación de descuentos y listado de aprobadores.  
- **Core/Configuración/Auditoría (`apps/core`)**: configuración empresa, configuración de facturación, impuestos y consulta/archivo de auditoría.

### Frontend (React + Vite + TypeScript)
- **Rutas principales**: login, dashboard, configuración, perfil, notificaciones, listados maestros, artículos, taller, ventas, cuentas del día, detalle de cuentas, facturas, remisiones, caja.  
- **Módulo Ventas (`pages/Ventas.tsx`)**: armado de carrito, búsqueda de cliente/producto, creación/edición de ventas, envío a caja y facturación.  
- **Módulo Artículos (`pages/Articulos.tsx`)**: consulta y mantenimiento de inventario (productos/categorías/proveedores), stock bajo, ajuste por acciones de inventario.  
- **Módulo Taller (`pages/Taller.tsx`)**: gestión de moto/orden, alta de cliente desde taller, agregar/quitar repuestos y facturar orden.  
- **Facturación (`pages/Facturas.tsx`, `pages/Remisiones.tsx`, `pages/Caja.tsx`)**: listados, detalle, anulación y facturación en caja.  
- **Configuración (`pages/Configuracion.tsx`)**: empresa, facturación, impuestos, auditoría y administración de usuarios.

### Comunicación frontend ↔ backend
- **Base API**: `/api` (proxy de Vite).  
- **Autenticación**: JWT con `/api/auth/login/` y `/api/auth/refresh/`.  
- **Autorización en frontend**: token en `localStorage`; el frontend usa dos claves (`token` y `access_token`) según módulo/cliente HTTP.  
- **Flujos principales de estado**: ventas pasan por estados `BORRADOR` → `ENVIADA_A_CAJA` → `FACTURADA` o `ANULADA`; taller puede generar venta facturada; anulación registra evento y devuelve inventario cuando aplica.

---

## 2) Inventario de endpoints (backend)

> Base común de router: `/api/`

### Inventario
- `categorias/` — `GET/POST` — listar/crear categoría — **crítico**: no — custom: `activas` (`GET categorias/activas/`).
- `categorias/{id}/` — `GET/PUT/PATCH/DELETE` — detalle/actualización/eliminación lógica — **crítico**: no.
- `proveedores/` — `GET/POST` — listar/crear proveedor — **crítico**: no — custom: `buscar_por_nit` (`GET proveedores/buscar_por_nit/`).
- `proveedores/{id}/` — `GET/PUT/PATCH/DELETE` — CRUD proveedor — **crítico**: no.
- `productos/` — `GET/POST` — listar/crear producto — **crítico**: sí (datos base de inventario).
- `productos/{id}/` — `GET/PUT/PATCH/DELETE` — detalle/actualizar/eliminación lógica — **crítico**: sí.
- `productos/buscar_por_codigo/` — `GET` — búsqueda exacta por código — **crítico**: no.
- `productos/stock_bajo/` — `GET` — productos con stock <= mínimo — **crítico**: no.
- `productos/estadisticas/` — `GET` — métricas de inventario — **crítico**: no.
- `productos/por_categoria/` — `GET` — filtra por categoría — **crítico**: no.
- `productos/{id}/ajustar_stock/` — `POST` — ajuste manual de stock con movimiento — **crítico**: **sí (stock)**.
- `movimientos/` — `GET` — histórico de movimientos inventario — **crítico**: auditoría operativa, no muta.
- `movimientos/{id}/` — `GET` — detalle movimiento — **crítico**: no muta.
- `movimientos/por_producto/` — `GET` — movimientos de producto — **crítico**: no muta.
- `productos-favoritos/` — `GET/POST` — favoritos del usuario — **crítico**: no.
- `productos-favoritos/{id}/` — `DELETE` — eliminar favorito — **crítico**: no.

### Ventas/Caja
- `clientes/` — `GET/POST` — listar/crear cliente — **crítico**: no.
- `clientes/{id}/` — `GET/PUT/PATCH/DELETE` — CRUD cliente — **crítico**: no.
- `clientes/buscar_por_documento/` — `GET` — búsqueda por documento — **crítico**: no.
- `ventas/` — `GET/POST` — listar/crear venta — **crítico**: **sí (facturación/estado)**.
- `ventas/{id}/` — `GET/PUT/PATCH/DELETE` — detalle/edición/eliminación — **crítico**: sí.
- `ventas/remisiones_pendientes/` — `GET` — remisiones facturadas sin factura asociada — **crítico**: no muta.
- `ventas/{id}/convertir_a_factura/` — `POST` — convierte remisión en factura — **crítico**: **sí (facturación/estado)**.
- `ventas/{id}/anular/` — `POST` — anula venta/remisión y registra anulación — **crítico**: **sí (estado + posible stock)**.
- `ventas/{id}/enviar-a-caja/` — `POST` — cambia a `ENVIADA_A_CAJA` — **crítico**: **sí (estado de caja)**.
- `ventas/estadisticas/` — `GET` — métricas de ventas — **crítico**: no muta.
- `caja/pendientes/` — `GET` — facturas enviadas a caja pendientes — **crítico**: no muta.
- `caja/{id}/facturar/` — `POST` — facturación final en caja — **crítico**: **sí (factura + salida inventario)**.
- `solicitudes-descuento/` — `GET/POST` — listar/crear solicitudes — **crítico**: sí (control comercial).
- `solicitudes-descuento/{id}/` — `GET/PUT/PATCH/DELETE` — gestión por aprobador/vendedor — **crítico**: sí.

### Taller
- `mecanicos/` — `GET/POST` — listar/crear mecánicos — **crítico**: no.
- `mecanicos/{id}/` — `GET/PUT/PATCH/DELETE` — CRUD mecánico — **crítico**: no.
- `motos/` — `GET/POST` — listar/crear moto — **crítico**: no.
- `motos/{id}/` — `GET/PUT/PATCH/DELETE` — actualización/eliminación lógica — **crítico**: no.
- `ordenes-taller/` — `GET/POST` — listar/crear orden — **crítico**: sí (proceso operativo).
- `ordenes-taller/{id}/` — `GET/PUT/PATCH/DELETE` — gestión orden — **crítico**: sí.
- `ordenes-taller/{id}/agregar_repuesto/` — `POST` — agrega línea y movimiento de salida — **crítico**: **sí (stock)**.
- `ordenes-taller/{id}/quitar_repuesto/` — `POST` — quita línea y genera devolución — **crítico**: **sí (stock)**.
- `ordenes-taller/{id}/facturar/` — `POST` — crea venta desde orden y marca orden facturada — **crítico**: **sí (dinero/estado)**.

### Usuarios
- `usuarios/` — `GET/POST` — listar/crear usuarios — **crítico**: sí (acceso).
- `usuarios/{id}/` — `GET/PUT/PATCH/DELETE` — administración usuario — **crítico**: sí.
- `usuarios/{id}/change_password/` — `POST` — cambio de contraseña — **crítico**: **sí (seguridad)**.
- `usuarios/validar_descuento/` — `POST` — valida credenciales para aprobar descuento — **crítico**: **sí (control comercial)**.
- `usuarios/aprobadores/` — `GET` — lista admins/superusers activos — **crítico**: no muta.
- `usuarios/me/` — `GET/PATCH` — perfil actual — **crítico**: sí (datos de cuenta).

### Configuración/Auditoría + Auth
- `configuracion-empresa/` — `GET` (AllowAny) y `PUT/PATCH` autenticado — datos de empresa (incluye logo) — **crítico**: sí (identidad comercial).
- `configuracion-facturacion/` — `GET/PUT/PATCH` — prefijos, numeración, plantillas/notas — **crítico**: **sí (facturación)**.
- `impuestos/` — `GET/POST` y `impuestos/{id}/` — gestión impuestos — **crítico**: **sí (cálculo fiscal)**.
- `auditoria/` — `GET`, `auditoria/{id}/` `GET` — consulta trazas — **crítico**: no muta.
- `auditoria/retention/` — `GET` — parámetros retención — **crítico**: no muta.
- `auditoria/archivar/` — `POST` — archiva/purga auditoría (staff/superuser) — **crítico**: **sí (trazabilidad)**.
- `auth/login/` — `POST` — emite JWT + payload usuario — **crítico**: **sí (acceso)**.
- `auth/refresh/` — `POST` — refresco JWT — **crítico**: **sí (sesión)**.

---

## 3) Inventario de pantallas y flujos (frontend)

### Login
- **Pantalla**: `Login`.
- **Acciones críticas**: autenticación; carga de configuración empresa para branding.
- **Endpoints deducibles**: `POST /api/auth/login/`, `GET /api/configuracion-empresa/`.

### Dashboard
- **Pantalla**: `Dashboard` (resumen visual).
- **Acciones críticas**: navegación hacia módulos.
- **Endpoints deducibles**: no se identifican llamadas críticas directas en el análisis realizado.

### Artículos (inventario)
- **Pantalla**: `Articulos`.
- **Acciones críticas**: crear/editar/eliminar producto; búsqueda por código; consulta stock bajo; gestión categorías/proveedores.
- **Endpoints deducibles**: `productos/*`, `categorias/*`, `proveedores/*`, `productos/stock_bajo/`, `productos/estadisticas/`, `productos/{id}/ajustar_stock/`.

### Ventas
- **Pantalla**: `Ventas`.
- **Acciones críticas**: buscar/crear cliente, agregar productos, crear/editar venta, enviar a caja, facturar en caja, crear cotización/remisión/factura, solicitar descuento.
- **Endpoints deducibles**: `clientes/*`, `ventas/*`, `ventas/{id}/enviar-a-caja/`, `caja/{id}/facturar/`, `solicitudes-descuento/*`, `productos/buscar_por_codigo/`.

### Caja
- **Pantalla**: `Caja`.
- **Acciones críticas**: listar pendientes de caja, facturar, impresión de comprobante.
- **Endpoints deducibles**: `GET /api/caja/pendientes/`, `POST /api/caja/{id}/facturar/`, `configuracion-empresa/`, `configuracion-facturacion/`.

### Facturas
- **Pantalla**: `Facturas`.
- **Acciones críticas**: filtrar facturas, ver detalle, anular factura, imprimir.
- **Endpoints deducibles**: `GET /api/ventas/?tipo_comprobante=FACTURA`, `GET /api/ventas/{id}/`, `POST /api/ventas/{id}/anular/`.

### Remisiones
- **Pantalla**: `Remisiones`.
- **Acciones críticas**: filtrar remisiones, ver detalle, anular remisión, imprimir.
- **Endpoints deducibles**: `GET /api/ventas/?tipo_comprobante=REMISION`, `GET /api/ventas/{id}/`, `POST /api/ventas/{id}/anular/`.

### Taller
- **Pantalla**: `Taller`.
- **Acciones críticas**: crear/editar/eliminar motos, crear orden, agregar/quitar repuestos, facturar orden, crear cliente desde taller.
- **Endpoints deducibles**: `motos/*`, `mecanicos/*`, `ordenes-taller/*`, `ordenes-taller/{id}/agregar_repuesto/`, `ordenes-taller/{id}/quitar_repuesto/`, `ordenes-taller/{id}/facturar/`, `clientes/*`, `productos/*`.

### Listados
- **Pantalla**: `Listados`.
- **Acciones críticas**: CRUD de entidades maestras (clientes, proveedores, categorías, usuarios, mecánicos).
- **Endpoints deducibles**: `clientes/*`, `proveedores/*`, `categorias/*`, `usuarios/*`, `mecanicos/*`.

### Configuración
- **Pantalla**: `Configuracion`.
- **Acciones críticas**: actualizar datos empresa/facturación, gestionar impuestos, auditar, archivar auditoría, crear/editar usuarios, cambiar contraseña.
- **Endpoints deducibles**: `configuracion-empresa/*`, `configuracion-facturacion/*`, `impuestos/*`, `auditoria/*`, `auditoria/archivar/`, `usuarios/*`, `usuarios/{id}/change_password/`, `usuarios/aprobadores/`, `usuarios/me/`.

### Notificaciones
- **Pantalla**: `Notificaciones`.
- **Acciones críticas**: revisar/aprobar/rechazar solicitudes de descuento (según rol).
- **Endpoints deducibles**: `solicitudes-descuento/` y `solicitudes-descuento/{id}/`.

### Mi Perfil
- **Pantalla**: `MiPerfil`.
- **Acciones críticas**: actualización de perfil actual.
- **Endpoints deducibles**: `GET/PATCH /api/usuarios/me/`.

### Cuentas del día / Detalles de cuentas
- **Pantallas**: `CuentasDia`, `DetallesCuentas`.
- **Acciones críticas**: consulta de estadísticas y ventas por fecha; impresión de resumen.
- **Endpoints deducibles**: `GET /api/ventas/estadisticas/`, `GET /api/ventas/`.

---

## 4) Flujos críticos transversales

### Flujo: Venta → Caja → Factura
- **Inicio UI**: `Ventas` (creación/edición) y luego `Caja`.
- **Endpoints**:
  1. `POST /api/ventas/` (creación en BORRADOR para FACTURA).
  2. `POST /api/ventas/{id}/enviar-a-caja/`.
  3. `POST /api/caja/{id}/facturar/`.
- **Mutaciones críticas**:
  - Estado de venta (`BORRADOR` → `ENVIADA_A_CAJA` → `FACTURADA`).
  - Registro de salida en inventario durante facturación (`MovimientoInventario` tipo SALIDA).
  - Trazas de usuario que envía/factura.

### Flujo: Taller → Venta → Factura/Remisión
- **Inicio UI**: `Taller`.
- **Endpoints**:
  1. `POST /api/ordenes-taller/` (crear orden).
  2. `POST /api/ordenes-taller/{id}/agregar_repuesto/` (afecta inventario con SALIDA).
  3. `POST /api/ordenes-taller/{id}/facturar/` (crea `Venta` en estado FACTURADA).
- **Mutaciones críticas**:
  - Stock al agregar/quitar repuestos.
  - Creación de venta asociada y cambio de estado de orden a `FACTURADO`.

### Flujo: Remisión → Factura
- **Inicio UI**: ventas/remisiones (operación sobre remisión facturada).
- **Endpoints**:
  1. `POST /api/ventas/{id}/convertir_a_factura/`.
- **Mutaciones críticas**:
  - Crea nueva venta tipo FACTURA con `remision_origen`.
  - Estado de factura creada en `FACTURADA`.
  - En detalles copiados, `afecto_inventario=False` para no descontar stock nuevamente.

### Flujo: Anulación → Devolución de stock
- **Inicio UI**: `Facturas` o `Remisiones`.
- **Endpoints**:
  1. `POST /api/ventas/{id}/anular/`.
- **Mutaciones críticas**:
  - Estado de venta/remisión a `ANULADA`.
  - Registro de `VentaAnulada` o `RemisionAnulada`.
  - Si aplica inventario: creación de movimientos `DEVOLUCION` y restitución de stock.

---

## 5) Riesgos técnicos detectables (sin soluciones)

### Lógica
1. **Doble vía de actualización de stock (vista + signal)**
   - Dónde: ajustes de stock y otros movimientos en inventario/taller/ventas.
   - Riesgo: mismo efecto de stock se realiza por signal post-save y en algunos métodos también se manipula `producto.stock` explícitamente.
   - Posible error en producción: inconsistencias de stock ante condiciones de carrera o mantenimiento evolutivo.

2. **Facturación de orden de taller crea venta FACTURADA sin pasar por flujo de caja**
   - Dónde: `ordenes-taller/{id}/facturar/`.
   - Riesgo: dos caminos de facturación con reglas diferentes (caja vs taller).
   - Posible error: divergencias operativas en conciliación de caja/reportes.

3. **Anulación ignora valor entrante de `devuelve_inventario`**
   - Dónde: acción `ventas/{id}/anular/` fija `devuelve_inventario = True`.
   - Riesgo: comportamiento distinto al payload esperado por cliente.
   - Posible error: devoluciones de stock no deseadas.

### Seguridad a nivel de código
1. **Configuración de empresa lectura pública (AllowAny)**
   - Dónde: `ConfiguracionEmpresaViewSet` (`list`/`retrieve`).
   - Riesgo: exposición de datos empresariales a consumidores no autenticados.
   - Posible error: filtración de datos de identificación/contacto.

2. **Validación de descuento requiere credenciales en payload**
   - Dónde: `usuarios/validar_descuento/`.
   - Riesgo: manejo de usuario/contraseña adicional dentro de flujo operativo.
   - Posible error: exposición accidental por logs o errores de cliente.

### Integración frontend ↔ backend
1. **Uso mixto de `token` y `access_token`**
   - Dónde: `AuthContext`, `api/client.ts`, y varios módulos API con `fetch`.
   - Riesgo: clientes diferentes pueden tomar tokens distintos según estado local.
   - Posible error: fallas intermitentes de autenticación (401 en algunos módulos).

2. **Uso mixto de `fetch` y `axios`**
   - Dónde: capa API del frontend.
   - Riesgo: comportamiento inconsistente de interceptores, parsing de errores y refresh de token.
   - Posible error: manejo heterogéneo de errores y sesiones vencidas.

### Rendimiento
1. **Carga frecuente del usuario actual cada 60s + al volver a foco**
   - Dónde: `AuthContext`.
   - Riesgo: polling continuo en sesiones largas.
   - Posible error: sobrecarga innecesaria del endpoint `usuarios/me`.

2. **Listados potencialmente extensos sin paginación uniforme en frontend**
   - Dónde: varios módulos consumen respuestas arreglo o paginadas de forma dual.
   - Riesgo: consumo de memoria/tiempo en tablas grandes.
   - Posible error: degradación de UI en datasets altos.

### UX con impacto operativo
1. **Mensajes de error heterogéneos**
   - Dónde: múltiples APIs frontend (`throw error`, `throw new Error(JSON.stringify(error))`, etc.).
   - Riesgo: respuestas no normalizadas al usuario final.
   - Posible error: operadores no distinguen causa real (permiso, validación, disponibilidad).

2. **Flujos de anulación/estado dependen de reglas de backend no visibles en UI**
   - Dónde: facturas/remisiones/caja.
   - Riesgo: intentos de operación inválidos según estado real.
   - Posible error: retrabajo operativo por rechazos repetidos de acciones.

---

## 6) Versionado (estado actual)

- **API versionada**: no se observa prefijo de versión (`/api/v1`); la API opera en `/api/`.
- **Contratos implícitos en frontend**:
  - El frontend asume nombres exactos de campos (`estado`, `tipo_comprobante`, `facturada_at`, `cliente_info`, etc.).
  - Asume existencia de acciones custom con rutas estables (`enviar-a-caja`, `convertir_a_factura`, `ajustar_stock`, etc.).
  - Asume semántica de estados de venta y tipos de comprobante para habilitar acciones.
- **Puntos donde un cambio rompería compatibilidad**:
  - Renombrar campos/enum en serializadores de ventas, taller, inventario o usuario.
  - Cambiar rutas de acciones custom (`@action`) usadas explícitamente por el frontend.
  - Modificar payload de login (estructura de `user`, tokens) o de respuestas de listados (array vs paginado).
  - Alterar reglas de transición de estados sin alinear llamadas frontend.
