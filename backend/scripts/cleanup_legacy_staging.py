#!/usr/bin/env python
"""Drop legacy staging tables (legacy_*) after validation."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

import django
from django.db import connection, transaction


LOGGER = logging.getLogger(__name__)


def setup_django() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def list_legacy_tables() -> List[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE 'legacy\\_%'
            ORDER BY table_name
            """
        )
        return [row[0] for row in cursor.fetchall()]


def drop_tables(tables: List[str]) -> None:
    if not tables:
        return
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {quote(table)};")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="Elimina las tablas staging")
    parser.add_argument("--dry-run", action="store_true", help="Simula la limpieza (default)")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    dry_run = not args.commit or args.dry_run

    setup_django()
    tables = list_legacy_tables()
    if not tables:
        LOGGER.info("No se encontraron tablas legacy_*. Nada que eliminar.")
        return

    LOGGER.info("Tablas legacy_ detectadas: %s", ", ".join(tables))
    with transaction.atomic():
        if dry_run:
            LOGGER.warning("Dry-run activo: no se eliminarán tablas.")
        else:
            drop_tables(tables)
            LOGGER.warning("Eliminadas %s tablas legacy_*. ", len(tables))

        if dry_run:
            transaction.set_rollback(True)


if __name__ == "__main__":
    main()
