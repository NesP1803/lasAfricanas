# LEGACY -> APP Mapping (staging)

Este documento describe el mapeo previsto desde los XLSX legacy (Access) hacia las tablas actuales de Django.
La carga se divide en dos fases:

1. **Importación a staging** (`legacy_*`)
2. **Migración a tablas reales** (apps Django)

> Nota: los XLSX del repo están versionados vía Git LFS. Los encabezados reales se determinan en tiempo de ejecución.
> El script usa listas de “candidatos” para encontrar columnas equivalentes.

## Orden de carga recomendado

1. **Catálogos**
   - Impuestos
   - Categorías
2. **Maestros**
   - Usuarios/Vendedores
   - Clientes
   - Productos
   - Mecánicos
   - Motos
3. **Documentos**
   - Facturas
   - Remisiones
   - Cotizaciones
4. **Detalles**
   - Detalles de facturas/remisiones
5. **Post-procesos**
   - Anulaciones

## Tablas legacy incluidas en staging

> Todas las tablas `dbo_*.xlsx` (excepto `dbo_View_*`) se cargan como `legacy_<nombre>`.

Ejemplos:
- `dbo_articulos.xlsx` -> `legacy_dbo_articulos`
- `dbo_facturas.xlsx` -> `legacy_dbo_facturas`
- `dbo_DetallesFactura.xlsx` -> `legacy_dbo_detallesfactura`

## Mapeo a modelos Django

### Catálogos

| Legacy staging | Modelo destino | Campos destino | Notas |
| --- | --- | --- | --- |
| `legacy_dbo_impuestos` | `core.Impuesto` | `nombre`, `valor`, `porcentaje`, `es_exento` | Se buscan columnas `impuesto`, `nombre`, `valor`, `porcentaje`/`iva`. |
| `legacy_dbo_ivas` | `core.Impuesto` | Igual que arriba | Se trata como otra fuente de impuestos. |
| `legacy_dbo_ivas_r` | `core.Impuesto` | Igual que arriba | Se trata como otra fuente de impuestos. |
| `legacy_dbo_categorias` | `inventario.Categoria` | `nombre`, `descripcion`, `orden` | Se toma `categoria`/`nombre`/`descripcion`. |
| `legacy_dbo_categorias_fac` | `inventario.Categoria` | Igual que arriba | Categorías de facturación (si aplica). |
| `legacy_dbo_rem_categorias` | `inventario.Categoria` | Igual que arriba | Categorías para remisiones. |

### Maestros

| Legacy staging | Modelo destino | Campos destino | Notas |
| --- | --- | --- | --- |
| `legacy_dbo_usuarios` | `usuarios.Usuario` | `username`, `email`, `first_name`, `last_name`, `tipo_usuario` | Se ignora `admin`. Password marcado como unusable. |
| `legacy_dbo_vendedores` | `usuarios.Usuario` | Igual que arriba | Se usa como fuente adicional de usuarios/vendedores. |
| `legacy_dbo_empleados` | `taller.Mecanico` | `nombre`, `telefono`, `email`, `direccion`, `ciudad` | Se mapea a mecánicos por nombre. |
| `legacy_dbo_contactos` | `ventas.Cliente` | `numero_documento`, `nombre`, `telefono`, `email`, `direccion`, `ciudad` | Usa columnas tipo `documento/cedula/nit`. |
| `legacy_dbo_contactos1` | `ventas.Cliente` | Igual que arriba | Fuente adicional de contactos. |
| `legacy_migrarclientes` | `ventas.Cliente` | Igual que arriba | Dependiendo de disponibilidad en staging. |
| `legacy_dbo_articulos` | `inventario.Producto` | `codigo`, `nombre`, `categoria`, `proveedor`, `precio_costo`, `precio_venta`, `stock`, `iva` | Valores por defecto para campos requeridos si faltan. |
| `legacy_dbo_articulos1` | `inventario.Producto` | Igual que arriba | Fuente adicional de productos. |
| `legacy_dbo_motos_registradas` | `taller.Moto` | `placa`, `marca`, `modelo`, `color`, `cliente`, `mecanico` | Vincula cliente por documento si existe. |

### Documentos

| Legacy staging | Modelo destino | Campos destino | Notas |
| --- | --- | --- | --- |
| `legacy_dbo_facturas` | `ventas.Venta` | `numero_comprobante`, `cliente`, `vendedor`, `subtotal`, `iva`, `total`, `medio_pago`, `estado` | `tipo_comprobante = FACTURA`. |
| `legacy_dbo_remisiones` | `ventas.Venta` | Igual que arriba | `tipo_comprobante = REMISION`. |
| `legacy_dbo_remisiones1` | `ventas.Venta` | Igual que arriba | `tipo_comprobante = REMISION`. |
| `legacy_dbo_cotizaciones` | `ventas.Venta` | Igual que arriba | `tipo_comprobante = COTIZACION`. |

### Detalles

| Legacy staging | Modelo destino | Campos destino | Notas |
| --- | --- | --- | --- |
| `legacy_dbo_detallesfactura` | `ventas.DetalleVenta` | `venta`, `producto`, `cantidad`, `precio_unitario`, `iva_porcentaje`, `subtotal`, `total` | Se busca venta por número de comprobante. |
| `legacy_dbo_detallesremision` | `ventas.DetalleVenta` | Igual que arriba | `tipo_comprobante = REMISION`. |
| `legacy_dbo_detallesremision1` | `ventas.DetalleVenta` | Igual que arriba | `tipo_comprobante = REMISION`. |

### Post-procesos

| Legacy staging | Modelo destino | Campos destino | Notas |
| --- | --- | --- | --- |
| `legacy_dbo_anulaciones_facturas` | `ventas.VentaAnulada` | `venta`, `motivo`, `descripcion`, `anulado_por` | `anulado_por` usa admin por defecto. |
| `legacy_dbo_anulaciones_remisiones` | `ventas.VentaAnulada` | Igual que arriba | |

## Tablas legacy sin mapeo directo (por ahora)

- `dbo_compras`, `dbo_descargas_articulos`, `dbo_preFactura`, `dbo_rem_resumenIVA`,
  `dbo_resumen_iva_fac`, `dbo_estados_fac`, `dbo_rem_estados`, `dbo_rem_mediopago`,
  `dbo_mediopago_fac`, `dbo_etiquetas`, `dbo_numeracion_fac`, `dbo_datosempresa`,
  `dbo_auditoria`, `dbo_filtro_fecha`, `dbo_usuarios` (si no mapea a Usuario), etc.

Estas tablas quedan disponibles en staging para análisis posterior.

## Ejecución

```bash
# Importar XLSX a staging (simulación)
python backend/scripts/import_legacy_stage.py --dry-run

# Importar XLSX a staging (commit real)
python backend/scripts/import_legacy_stage.py --commit

# Migrar staging a tablas reales (simulación)
python backend/scripts/migrate_legacy_to_app.py --dry-run

# Migrar staging a tablas reales (commit real)
python backend/scripts/migrate_legacy_to_app.py --commit
```
