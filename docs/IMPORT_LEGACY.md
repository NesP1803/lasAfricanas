# Import legacy (Access XLSX) -> PostgreSQL (Django)

## Repo stack
- Backend: Django + PostgreSQL
- Frontend: React (Vite + TypeScript)

## Current DB state
- Migraciones aplicadas, tablas ya existen.
- Tablas vacías excepto el usuario admin de prueba.
- NO borrar ni truncar tablas actuales.
- NO modificar/eliminar el admin.

## Legacy data
XLSX del sistema anterior están en `data/` (dbo_*.xlsx)

## Goal
Codex debe:
1) Revisar modelos/migraciones Django y consumo desde frontend.
2) Revisar XLSX legacy.
3) Definir mapeo dbo_* -> tablas actuales.
4) Importar sin confusión usando STAGING.
5) Auditar duplicados e integridad antes/después de la migración.

## Required strategy
- Crear tablas staging `legacy_*` (una por cada XLSX).
- Script 1: `backend/scripts/import_legacy_stage.py` (XLSX -> legacy_*)
- Script 2: `backend/scripts/migrate_legacy_to_app.py` (legacy_* -> tablas reales)
- Script 3: `backend/scripts/audit_legacy_data.py` (auditoría de duplicados e integridad)
- Ambos scripts con `--dry-run` y `--commit`, logs y transacciones.
- Ignorar `dbo_View_*` (son vistas del sistema viejo).

## Auditoría recomendada

1) Cargar XLSX a staging.
2) Ejecutar auditoría para detectar duplicados en staging.
3) Migrar a tablas reales.
4) Ejecutar auditoría para detectar duplicados y ventas sin detalles.
5) Unificar duplicados en staging antes de migrar si se detectan claves repetidas.
6) Cuando todo esté validado, eliminar staging.

```bash
# Desde la raíz del repo
python backend/scripts/audit_legacy_data.py --limit 20

# Desde la carpeta backend/
python scripts/audit_legacy_data.py --limit 20
```

## Limpieza de duplicados en staging (legacy_*)

Este paso elimina filas duplicadas en tablas legacy (staging) usando columnas clave
y conserva la fila con más columnas llenas.
Por defecto es **dry-run** y no aplica cambios.

```bash
# Simulación
python backend/scripts/clean_legacy_duplicates.py --dry-run

# Aplicar cambios
python backend/scripts/clean_legacy_duplicates.py --commit
```

## Checklist de validación antes de borrar staging

1) Ejecutar auditoría y revisar advertencias (`audit_legacy_data.py`).
2) Ejecutar limpieza de duplicados en staging si hay claves repetidas (`clean_legacy_duplicates.py`).
3) Migrar a tablas reales (`migrate_legacy_to_app.py --commit`).
4) Re-ejecutar auditoría y confirmar que no hay duplicados en tablas reales.
5) Validar en el frontend que clientes, productos y ventas se muestren correctamente.
6) Hacer backup de la base de datos si todo está correcto.
7) Eliminar staging con el script de limpieza.

## Eliminar staging (legacy_*) cuando ya no se necesita

```bash
# Simulación
python backend/scripts/cleanup_legacy_staging.py --dry-run

# Aplicar cambios
python backend/scripts/cleanup_legacy_staging.py --commit
```
