#!/usr/bin/env python
"""Audit legacy staging vs app tables for duplicates and orphaned data."""
from __future__ import annotations

import argparse
import logging
import os
from typing import Iterable, List, Sequence, Tuple

import django
from django.db import connection


LOGGER = logging.getLogger(__name__)


def setup_django() -> None:
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


def fetch_duplicates(table: str, columns: Sequence[str], limit: int) -> List[Tuple[Tuple[object, ...], int]]:
    if not columns:
        return []
    quote = connection.ops.quote_name
    column_sql = ", ".join(quote(col) for col in columns)
    sql = (
        f"SELECT {column_sql}, COUNT(*) "
        f"FROM {quote(table)} "
        f"GROUP BY {column_sql} "
        f"HAVING COUNT(*) > 1 "
        f"ORDER BY COUNT(*) DESC "
        f"LIMIT %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [limit])
        rows = cursor.fetchall()
    return [((tuple(row[:-1])), row[-1]) for row in rows]


def report_duplicates(table: str, columns: Sequence[str], limit: int) -> None:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return
    usable_cols = available_columns(table, columns)
    if not usable_cols:
        LOGGER.info("Tabla %s no tiene columnas candidatas (%s)", table, ", ".join(columns))
        return
    duplicates = fetch_duplicates(table, usable_cols, limit)
    if not duplicates:
        LOGGER.info("Sin duplicados en %s usando %s", table, ", ".join(usable_cols))
        return
    LOGGER.warning("Duplicados detectados en %s usando %s", table, ", ".join(usable_cols))
    for values, count in duplicates:
        display = ", ".join(str(value) for value in values)
        LOGGER.warning("  (%s) -> %s registros", display, count)


def count_rows(table: str) -> int:
    if not table_exists(table):
        return 0
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {quote(table)}")
        return int(cursor.fetchone()[0])


def check_ventas_sin_detalles() -> None:
    if not table_exists("ventas") or not table_exists("detalles_venta"):
        return
    quote = connection.ops.quote_name
    sql = f"""
        SELECT v.tipo_comprobante, COUNT(*)
        FROM {quote("ventas")} v
        LEFT JOIN {quote("detalles_venta")} d ON d.venta_id = v.id
        GROUP BY v.id, v.tipo_comprobante
        HAVING COUNT(d.id) = 0
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
    if not rows:
        LOGGER.info("Todas las ventas tienen al menos un detalle.")
        return
    totals = {}
    for tipo, _ in rows:
        totals[tipo] = totals.get(tipo, 0) + 1
    for tipo, total in totals.items():
        LOGGER.warning("Ventas sin detalles (%s): %s", tipo, total)


def check_anulaciones_sin_ventas() -> None:
    if not table_exists("ventas_anuladas"):
        return
    quote = connection.ops.quote_name
    sql = f"""
        SELECT COUNT(*)
        FROM {quote("ventas_anuladas")} va
        LEFT JOIN {quote("ventas")} v ON v.id = va.venta_id
        WHERE v.id IS NULL
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        missing = int(cursor.fetchone()[0])
    if missing:
        LOGGER.warning("Anulaciones sin venta asociada: %s", missing)
    else:
        LOGGER.info("Todas las anulaciones tienen venta asociada.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="Máximo de duplicados listados por tabla")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    setup_django()

    LOGGER.info("=== Resumen de filas en staging ===")
    staging_tables = [
        "legacy_dbo_impuestos",
        "legacy_dbo_ivas",
        "legacy_dbo_ivas_r",
        "legacy_dbo_categorias",
        "legacy_dbo_categorias_fac",
        "legacy_dbo_rem_categorias",
        "legacy_dbo_usuarios",
        "legacy_dbo_vendedores",
        "legacy_dbo_empleados",
        "legacy_dbo_contactos",
        "legacy_dbo_contactos1",
        "legacy_migrarclientes",
        "legacy_dbo_articulos",
        "legacy_dbo_articulos1",
        "legacy_dbo_motos_registradas",
        "legacy_dbo_facturas",
        "legacy_dbo_remisiones",
        "legacy_dbo_remisiones1",
        "legacy_dbo_cotizaciones",
        "legacy_dbo_detallesfactura",
        "legacy_dbo_detallesremision",
        "legacy_dbo_detallesremision1",
        "legacy_dbo_anulaciones_facturas",
        "legacy_dbo_anulaciones_remisiones",
    ]
    for table in staging_tables:
        if table_exists(table):
            LOGGER.info("%s: %s filas", table, count_rows(table))

    LOGGER.info("=== Duplicados potenciales en staging ===")
    report_duplicates(
        "legacy_dbo_contactos",
        ["documento", "cedula", "nit", "numero_documento", "identificacion", "idcliente", "clienteid"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_contactos1",
        ["documento", "cedula", "nit", "numero_documento", "identificacion", "idcliente", "clienteid"],
        args.limit,
    )
    report_duplicates(
        "legacy_migrarclientes",
        ["documento", "cedula", "nit", "numero_documento", "identificacion", "idcliente", "clienteid"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_articulos",
        ["codigo", "sku", "referencia", "id", "cod"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_articulos1",
        ["codigo", "sku", "referencia", "id", "cod"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_facturas",
        ["prefijo", "nofactura", "no_factura", "factura", "numero", "num", "numero_comprobante"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_remisiones",
        ["noremision", "no_remision", "remision", "numero", "num", "numero_comprobante"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_cotizaciones",
        ["numero", "cotizacion", "num", "numero_comprobante"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_detallesfactura",
        ["nofactura", "factura", "numero", "num", "codigo", "referencia", "id"],
        args.limit,
    )
    report_duplicates(
        "legacy_dbo_detallesremision",
        ["noremision", "remision", "numero", "num", "codigo", "referencia", "id"],
        args.limit,
    )

    LOGGER.info("=== Duplicados potenciales en tablas app ===")
    report_duplicates("clientes", ["numero_documento"], args.limit)
    report_duplicates("productos", ["codigo"], args.limit)
    report_duplicates("ventas", ["numero_comprobante"], args.limit)
    report_duplicates("detalles_venta", ["venta_id", "producto_id", "precio_unitario", "cantidad"], args.limit)

    LOGGER.info("=== Integridad en tablas app ===")
    check_ventas_sin_detalles()
    check_anulaciones_sin_ventas()


if __name__ == "__main__":
    main()
