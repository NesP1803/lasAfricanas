# Auditoría responsive y plan aplicado — LAS AFRICANAS

Fecha: 2026-04-02

## 1) Diagnóstico técnico del estado actual

### Hallazgos críticos (P1)
1. **Tablas operativas con anchos mínimos rígidos y densidad alta** en facturas/remisiones/ventas, causando uso complejo en móvil y tablet vertical.
2. **Modales complejos sin patrón unificado de altura/scroll interno**; riesgo de doble scroll y botones fuera de viewport en móvil.
3. **Filtros densos en filas horizontales** (listados de facturación), con colisiones de controles en breakpoints intermedios.

### Hallazgos importantes (P2)
1. **Layout principal sin contenedor máximo estandarizado** para pantallas ultraanchas.
2. **Menú móvil sin límite de alto + scroll explícito** en navegación extensa.
3. **Inconsistencia de spacing entre pantallas**, generando variación de densidad visual.

### Hallazgos de mejora (P3)
1. Falta de clases utilitarias compartidas para tablas/modales/filtros.
2. Tap targets mejorables en acciones secundarias en móvil.

## 2) Estrategia responsive unificada aplicada

- Enfoque: **mobile-first híbrido** con componentes operativos conservados.
- Se estandarizaron utilidades reutilizables:
  - `app-shell-main` (ancho máximo + paddings consistentes)
  - `app-filters-grid` (filtros en grid adaptable)
  - `app-table-shell` + `app-table-scroll` (tabla robusta con overflow controlado)
  - `app-modal-backdrop`, `app-modal-panel-md/lg`, `app-modal-body` (modales con scroll interno estable)
- Reglas en móvil:
  - inputs/buttons con tamaño de fuente no inferior a 16px para evitar zoom involuntario.

## 3) Cambios aplicados

### Layout y navegación
- Contenedor principal responsive centralizado.
- Navegación desktop con padding más flexible.
- Menú móvil con `max-height` y `overflow-y-auto`.

### Listados operativos
- Facturas y Remisiones: filtros migrados a grid responsive.
- Facturas y Remisiones: estandarización de contenedor de tabla y overflow.
- Ajuste de anchos mínimos para mantener operatividad y reducir scroll extremo.

### Modales
- Estandarización en ConfirmModal.
- Estandarización de modales críticos en Facturas y Remisiones.

### Venta rápida
- Contenedor de tabla principal migrado a patrón shared (`app-table-scroll`) y min-width operativo para no romper columnas.

## 4) Rendimiento y estabilidad

- No se alteró lógica de negocio ni permisos/rutas/moduleAccess.
- Cambios centrados en **estilos/estructura de layout** para evitar regresiones funcionales.
- Se validó compilación de assets con `vite build`.
- Se detectó deuda previa de tipado TS no relacionada con este ajuste (notas crédito).

## 5) Módulos revisados (cobertura)

- Layout global
- Venta rápida
- Facturas
- Remisiones
- Confirmación modal global
- Base de estilos globales

> Nota: esta iteración consolida la base transversal responsive y corrige los flujos más críticos de facturación/venta. Recomendada segunda iteración para completar el mismo patrón en Configuración, Taller, Artículos, Listados y modales secundarios.
