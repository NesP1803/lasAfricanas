#!/usr/bin/env python
"""Auditoría post-migración legacy: duplicados, huérfanos lógicos y conteos."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import django
from django.db import connection

LOGGER = logging.getLogger(__name__)


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--tables",
        nargs="*",
        default=[
            "staging_dbo_categorias",
            "staging_dbo_articulos",
            "staging_dbo_contactos",
            "staging_dbo_datosempresa",
            "staging_dbo_empleados",
            "staging_dbo_impuestos",
            "staging_dbo_motos_registradas",
        ],
    )
    return parser.parse_args()


def table_exists(table: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name=%s
            )
            """,
            [table],
        )
        return bool(cursor.fetchone()[0])


def count_rows(table: str) -> int:
    if not table_exists(table):
        return 0
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {quote(table)}")
        return int(cursor.fetchone()[0])


def log_duplicates(table: str, columns: list[str], limit: int) -> None:
    if not table_exists(table):
        LOGGER.warning("Tabla no existe: %s", table)
        return
    quote = connection.ops.quote_name
    cols = ", ".join(quote(c) for c in columns)
    sql = (
        f"SELECT {cols}, COUNT(*) AS n "
        f"FROM {quote(table)} "
        f"GROUP BY {cols} "
        f"HAVING COUNT(*) > 1 "
        f"ORDER BY n DESC "
        f"LIMIT %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [limit])
        rows = cursor.fetchall()
    if not rows:
        LOGGER.info("Sin duplicados en %s por (%s)", table, ", ".join(columns))
        return
    LOGGER.warning("Duplicados en %s por (%s): %s grupos", table, ", ".join(columns), len(rows))
    for row in rows:
        LOGGER.warning("  key=%s repeticiones=%s", row[:-1], row[-1])


def query_scalar(sql: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return int(cursor.fetchone()[0] or 0)


def audit_relationships() -> None:
    productos_sin_categoria = query_scalar("SELECT COUNT(*) FROM productos WHERE categoria_id IS NULL")
    motos_sin_mecanico = query_scalar("SELECT COUNT(*) FROM motos WHERE mecanico_id IS NULL")
    productos_sin_proveedor = query_scalar("SELECT COUNT(*) FROM productos WHERE proveedor_id IS NULL")

    LOGGER.info("Productos sin categoría: %s", productos_sin_categoria)
    LOGGER.info("Motos sin mecánico: %s", motos_sin_mecanico)
    LOGGER.info("Productos sin proveedor: %s", productos_sin_proveedor)


def audit_expected_counts() -> None:
    LOGGER.info("=== Conteos staging -> app ===")
    pairs = [
        ("staging_dbo_categorias", "categorias"),
        ("staging_dbo_impuestos", "impuestos"),
        ("staging_dbo_articulos", "productos"),
        ("staging_dbo_contactos", "clientes"),
        ("staging_dbo_contactos", "proveedores"),
        ("staging_dbo_empleados", "mecanicos"),
        ("staging_dbo_motos_registradas", "motos"),
    ]
    for src, dst in pairs:
        LOGGER.info("%s=%s | %s=%s", src, count_rows(src), dst, count_rows(dst))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    setup_django()

    LOGGER.info("=== Conteo tablas staging seleccionadas ===")
    for table in args.tables:
        LOGGER.info("%s: %s", table, count_rows(table))

    LOGGER.info("=== Duplicados por llaves naturales (app) ===")
    log_duplicates("categorias", ["nombre"], args.limit)
    log_duplicates("productos", ["codigo"], args.limit)
    log_duplicates("clientes", ["numero_documento"], args.limit)
    log_duplicates("proveedores", ["nombre"], args.limit)
    log_duplicates("mecanicos", ["nombre"], args.limit)
    log_duplicates("motos", ["placa"], args.limit)

    LOGGER.info("=== Duplicados en staging (fuente) ===")
    log_duplicates("staging_dbo_articulos", ["codigo"], args.limit)
    log_duplicates("staging_dbo_contactos", ["id", "tipocontacto"], args.limit)
    log_duplicates("staging_dbo_motos_registradas", ["moto"], args.limit)

    LOGGER.info("=== Integridad relacional esperada ===")
    audit_relationships()

    audit_expected_counts()


if __name__ == "__main__":
    main()
