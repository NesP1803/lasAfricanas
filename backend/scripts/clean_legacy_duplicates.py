#!/usr/bin/env python
"""Remove duplicated rows from legacy staging tables, keeping the most complete row."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import django
from django.db import connection, transaction


LOGGER = logging.getLogger(__name__)


def setup_django() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def table_exists(table: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            [table],
        )
        return bool(cursor.fetchone()[0])


def get_columns(table: str) -> List[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            [table],
        )
        return [row[0] for row in cursor.fetchall()]


def available_columns(table: str, candidates: Sequence[str]) -> List[str]:
    existing = set(get_columns(table))
    return [col for col in candidates if col in existing]


def fetch_duplicate_rows(
    table: str,
    key_columns: Sequence[str],
    all_columns: Sequence[str],
) -> List[Tuple[str, Dict[str, object]]]:
    if not key_columns:
        return []
    quote = connection.ops.quote_name
    key_sql = ", ".join(quote(col) for col in key_columns)
    all_sql = ", ".join(quote(col) for col in all_columns)
    sql = f"""
        SELECT ctid::text, {all_sql}
        FROM {quote(table)}
        WHERE ({key_sql}) IN (
            SELECT {key_sql}
            FROM {quote(table)}
            GROUP BY {key_sql}
            HAVING COUNT(*) > 1
        )
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
    results: List[Tuple[str, Dict[str, object]]] = []
    for row in rows:
        ctid = row[0]
        values = dict(zip(all_columns, row[1:]))
        results.append((ctid, values))
    return results


def score_row(values: Iterable[object]) -> int:
    score = 0
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        score += 1
    return score


def delete_by_ctid(table: str, ctids: Sequence[str]) -> int:
    if not ctids:
        return 0
    quote = connection.ops.quote_name
    placeholders = ", ".join(["%s"] * len(ctids))
    sql = f"DELETE FROM {quote(table)} WHERE ctid::text IN ({placeholders})"
    with connection.cursor() as cursor:
        cursor.execute(sql, ctids)
        return cursor.rowcount


def dedupe_table(table: str, key_columns: Sequence[str], dry_run: bool) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    usable_keys = available_columns(table, key_columns)
    if not usable_keys:
        LOGGER.info("Tabla %s no tiene columnas candidatas (%s)", table, ", ".join(key_columns))
        return 0

    all_columns = get_columns(table)
    rows = fetch_duplicate_rows(table, usable_keys, all_columns)
    if not rows:
        LOGGER.info("Sin duplicados en %s usando %s", table, ", ".join(usable_keys))
        return 0

    grouped: Dict[Tuple[object, ...], List[Tuple[str, int]]] = defaultdict(list)
    for ctid, row in rows:
        key = tuple(row.get(col) for col in usable_keys)
        grouped[key].append((ctid, score_row(row.values())))

    deletions: List[str] = []
    for values, group in grouped.items():
        best_ctid, _ = max(group, key=lambda item: item[1])
        for ctid, _ in group:
            if ctid != best_ctid:
                deletions.append(ctid)

    deleted = 0
    if deletions:
        if dry_run:
            LOGGER.warning(
                "Dry-run: %s filas duplicadas serían eliminadas en %s",
                len(deletions),
                table,
            )
        else:
            deleted = delete_by_ctid(table, deletions)
            LOGGER.warning("Eliminadas %s filas duplicadas en %s", deleted, table)
    return deleted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="Aplica la limpieza")
    parser.add_argument("--dry-run", action="store_true", help="Simula la limpieza (default)")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    dry_run = not args.commit or args.dry_run

    setup_django()

    tables = [
        ("legacy_dbo_facturas", ["prefijo", "nofactura", "no_factura", "factura", "numero", "num"]),
        ("legacy_dbo_remisiones", ["noremision", "no_remision", "remision", "numero", "num"]),
        ("legacy_dbo_cotizaciones", ["numero", "cotizacion", "num"]),
        ("legacy_dbo_detallesfactura", ["factura", "nofactura", "numero", "num", "codigo", "referencia", "id"]),
        ("legacy_dbo_detallesremision", ["remision", "noremision", "numero", "num", "codigo", "referencia", "id"]),
        ("legacy_dbo_contactos", ["documento", "cedula", "nit", "numero_documento", "identificacion", "idcliente", "clienteid"]),
        ("legacy_migrarclientes", ["documento", "cedula", "nit", "numero_documento", "identificacion", "idcliente", "clienteid"]),
        ("legacy_dbo_articulos", ["codigo", "sku", "referencia", "id", "cod"]),
    ]

    LOGGER.info("Modo: %s", "COMMIT" if (args.commit and not args.dry_run) else "DRY-RUN")
    total_deleted = 0
    with transaction.atomic():
        for table, keys in tables:
            total_deleted += dedupe_table(table, keys, dry_run)
        if dry_run:
            LOGGER.warning("Dry-run activo: realizando rollback")
            transaction.set_rollback(True)

    LOGGER.info("Total filas eliminadas: %s", total_deleted)


if __name__ == "__main__":
    main()
