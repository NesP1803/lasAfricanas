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

```bash
# Desde la raíz del repo
python backend/scripts/audit_legacy_data.py --limit 20

# Desde la carpeta backend/
python scripts/audit_legacy_data.py --limit 20
```
