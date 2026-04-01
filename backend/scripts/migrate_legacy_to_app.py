#!/usr/bin/env python
"""Migra staging_* a tablas Django (enfoque conservador e idempotente)."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import django
from django.db import connection, transaction

from legacy_migration_utils import (
    IncidentLogger,
    normalize_code,
    normalize_document,
    normalize_email,
    normalize_string,
    parse_date,
    parse_decimal,
)

LOGGER = logging.getLogger(__name__)

# Models are loaded in setup_django
Categoria = Cliente = ConfiguracionEmpresa = Impuesto = Mecanico = Moto = None
Producto = Proveedor = Usuario = None


@dataclass
class Counter:
    inserted: int = 0
    updated: int = 0
    omitted: int = 0


def setup_django() -> None:
    global Categoria, Cliente, ConfiguracionEmpresa, Impuesto, Mecanico, Moto, Producto, Proveedor, Usuario
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from apps.core.models import ConfiguracionEmpresa as ConfiguracionEmpresaModel, Impuesto as ImpuestoModel
    from apps.inventario.models import Categoria as CategoriaModel, Producto as ProductoModel, Proveedor as ProveedorModel
    from apps.taller.models import Mecanico as MecanicoModel, Moto as MotoModel
    from apps.usuarios.models import Usuario as UsuarioModel
    from apps.ventas.models import Cliente as ClienteModel

    Categoria = CategoriaModel
    Cliente = ClienteModel
    ConfiguracionEmpresa = ConfiguracionEmpresaModel
    Impuesto = ImpuestoModel
    Mecanico = MecanicoModel
    Moto = MotoModel
    Producto = ProductoModel
    Proveedor = ProveedorModel
    Usuario = UsuarioModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="Confirma cambios")
    parser.add_argument("--dry-run", action="store_true", help="Forzar rollback")
    parser.add_argument(
        "--incidents-json",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "logs" / "legacy_migrate_incidents.json",
    )
    return parser.parse_args()


def table_exists(table: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name=%s
            )
            """,
            [table],
        )
        return bool(cursor.fetchone()[0])


def iter_table_rows(table: str, batch: int = 500):
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {quote(table)}")
        columns = [c[0] for c in cursor.description]
        while True:
            rows = cursor.fetchmany(batch)
            if not rows:
                break
            for row in rows:
                yield dict(zip(columns, row))


def row_value(row: dict[str, Any], *keys: str) -> str:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return normalize_string(row[k])
    return ""


def fit(value: str, max_len: int) -> str:
    value = normalize_string(value)
    return value[:max_len] if len(value) > max_len else value


def normalize_tipo_documento(sigla: str, tipoid: str) -> str:
    candidate = normalize_string(sigla, upper=True) or normalize_string(tipoid, upper=True)
    if candidate in {"NIT", "31"}:
        return "NIT"
    if candidate in {"CE", "22"}:
        return "CE"
    if candidate in {"PASAPORTE", "PAS"}:
        return "PASAPORTE"
    return "CC"


def maybe_get_user(username: str) -> Optional["Usuario"]:
    if not username:
        return None
    return Usuario.objects.filter(username__iexact=username).first()


def migrate_categorias(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_categorias"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return c

    for row in iter_table_rows(table):
        nombre = row_value(row, "categoria")
        key = nombre or f"row:{row.get('_source_row', '?')}"
        if not nombre:
            c.omitted += 1
            incidents.add("WARN", "MIGRATE", table, key, "Categoría vacía")
            continue
        obj, created = Categoria.objects.update_or_create(
            nombre=nombre,
            defaults={"descripcion": "", "orden": 0},
        )
        c.inserted += int(created)
        c.updated += int(not created and bool(obj.pk))
    return c


def migrate_impuestos(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_impuestos"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return c

    for row in iter_table_rows(table):
        nombre = row_value(row, "impuesto")
        if not nombre:
            c.omitted += 1
            continue
        obj, created = Impuesto.objects.update_or_create(
            nombre=nombre,
            defaults={"porcentaje": Decimal("0.00")},
        )
        c.inserted += int(created)
        c.updated += int(not created and bool(obj.pk))
    return c

        if not documento:
            incidents.add("WARN", "MIGRATE", table, key, "Cliente sin documento; omitido")
            result["clientes"].omitted += 1
            continue

def migrate_empresa(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_datosempresa"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return c

    best_row = None
    for row in iter_table_rows(table):
        if row_value(row, "razonsocial"):
            best_row = row
            break
    if not best_row:
        incidents.add("WARN", "MIGRATE", table, "", "Sin fila válida de empresa")
        c.omitted += 1
        return c

    identificacion = normalize_document(row_value(best_row, "nitcc", "id"))
    if not identificacion:
        incidents.add("ERROR", "MIGRATE", table, "empresa", "Identificación vacía; se omite")
        c.omitted += 1
        return c

    defaults = {
        "tipo_identificacion": normalize_tipo_documento(row_value(best_row, "siglaid"), row_value(best_row, "tipoid")),
        "dv": fit(row_value(best_row, "dv"), 1),
        "tipo_persona": "Persona jurídica" if "jur" in row_value(best_row, "tipopersona").lower() else "Persona natural",
        "razon_social": fit(row_value(best_row, "razonsocial") or "EMPRESA LEGACY", 200),
        "regimen": "RÉGIMEN COMÚN" if "com" in row_value(best_row, "regimen").lower() else "RÉGIMEN SIMPLIFICADO",
        "direccion": fit(row_value(best_row, "direccion"), 200),
        "ciudad": fit(row_value(best_row, "departamento") or "NO DEFINIDA", 100),
        "municipio": fit(row_value(best_row, "municipio") or "NO DEFINIDO", 100),
        "telefono": fit(row_value(best_row, "telefono"), 20),
        "sitio_web": fit(row_value(best_row, "web"), 200),
        "correo": fit(normalize_email(row_value(best_row, "correo")), 254),
    }

    current = ConfiguracionEmpresa.objects.first()
    if current:
        for k, v in defaults.items():
            setattr(current, k, v)
        current.identificacion = identificacion
        current.save()
        c.updated += 1
    else:
        ConfiguracionEmpresa.objects.create(identificacion=identificacion, **defaults)
        c.inserted += 1
    return c


def resolve_contact_role(tipocontacto: str) -> str:
    value = normalize_string(tipocontacto, upper=True)
    if "PROV" in value:
        return "PROVEEDOR"
    if any(token in value for token in ["CLI", "CLIENT"]):
        return "CLIENTE"
    return "AMBIGUO"


def contacto_nombre(row: dict[str, Any]) -> str:
    razon = row_value(row, "razonsocial")
    if razon:
        return razon
    parts = [
        row_value(row, "nombre1"),
        row_value(row, "nombre2"),
        row_value(row, "apellido1"),
        row_value(row, "apellido2"),
    ]
    return fit(" ".join(p for p in parts if p), 200)


def migrate_contactos(incidents: IncidentLogger) -> dict[str, Counter]:
    result = {"clientes": Counter(), "proveedores": Counter()}
    table = "staging_dbo_contactos"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return result

    for row in iter_table_rows(table):
        role = resolve_contact_role(row_value(row, "tipocontacto"))
        documento = fit(normalize_document(row_value(row, "id", "codigo")), 50)
        nombre = fit(contacto_nombre(row), 200)
        key = documento or nombre or f"row:{row.get('_source_row', '?')}"

        if role == "AMBIGUO":
            incidents.add("WARN", "MIGRATE", table, key, "tipocontacto ambiguo; fila omitida")
            result["clientes"].omitted += 1
            continue

        if not nombre:
            incidents.add("WARN", "MIGRATE", table, key, "Sin nombre/razón social")
            (result["proveedores"] if role == "PROVEEDOR" else result["clientes"]).omitted += 1
            continue

        if role == "PROVEEDOR":
            if not nombre:
                result["proveedores"].omitted += 1
                continue
            _, created = Proveedor.objects.update_or_create(
                nombre=nombre,
                defaults={
                    "nit": fit(documento, 20),
                    "telefono": fit(row_value(row, "telefono", "celular"), 20),
                    "email": fit(normalize_email(row_value(row, "correo")), 254),
                    "direccion": row_value(row, "direccion"),
                    "ciudad": fit(row_value(row, "ciudad"), 100),
                    "contacto": fit(nombre, 200),
                },
            )
            result["proveedores"].inserted += int(created)
            result["proveedores"].updated += int(not created)
            continue

        if not documento:
            incidents.add("WARN", "MIGRATE", table, key, "Cliente sin documento; omitido")
            result["clientes"].omitted += 1
            continue

        _, created = Cliente.objects.update_or_create(
            numero_documento=documento,
            defaults={
                "tipo_documento": normalize_tipo_documento(row_value(row, "siglaid"), row_value(row, "tipoid")),
                "nombre": fit(nombre, 200),
                "telefono": fit(row_value(row, "telefono", "celular"), 50),
                "email": fit(normalize_email(row_value(row, "correo")), 254),
                "direccion": row_value(row, "direccion"),
                "ciudad": fit(row_value(row, "ciudad"), 100),
            },
        )
        result["clientes"].inserted += int(created)
        result["clientes"].updated += int(not created)

    return result


def migrate_mecanicos(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_empleados"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return c

    for row in iter_table_rows(table):
        nombre = fit(row_value(row, "empleado"), 200)
        key = nombre or f"row:{row.get('_source_row', '?')}"
        if not nombre:
            incidents.add("WARN", "MIGRATE", table, key, "Empleado sin nombre")
            c.omitted += 1
            continue
        _, created = Mecanico.objects.update_or_create(
            nombre=nombre,
            defaults={
                "telefono": row_value(row, "telefono"),
                "email": fit(normalize_email(row_value(row, "correo")), 254),
                "direccion": row_value(row, "direccion"),
                "ciudad": fit("", 100),
            },
        )
        c.inserted += int(created)
        c.updated += int(not created)
    return c


def unit_choice(raw_um: str) -> str:
    val = normalize_string(raw_um, upper=True)
    if val in {"KG", "LT", "MT"}:
        return val
    return "N/A"


def migrate_productos(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_articulos"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return c

    categoria_default, _ = Categoria.objects.get_or_create(nombre="SIN CATEGORIA", defaults={"descripcion": "Legacy"})

    for row in iter_table_rows(table):
        codigo = fit(normalize_code(row_value(row, "codigo")), 50)
        nombre = fit(row_value(row, "articulo"), 300)
        key = codigo or f"row:{row.get('_source_row', '?')}"
        if not codigo or not nombre:
            incidents.add("WARN", "MIGRATE", table, key, "Producto sin código o nombre")
            c.omitted += 1
            continue

        categoria_nombre = row_value(row, "categoria")
        categoria = categoria_default
        if categoria_nombre:
            categoria, _ = Categoria.objects.get_or_create(nombre=fit(categoria_nombre, 100), defaults={"descripcion": "Legacy"})

        proveedor = None
        proveedor_nombre = row_value(row, "proveedor")
        if proveedor_nombre:
            proveedor, _ = Proveedor.objects.get_or_create(nombre=fit(proveedor_nombre, 200))

        precio_costo = parse_decimal(row_value(row, "precio"), default=Decimal("0.01"))
        precio_venta = parse_decimal(row_value(row, "precioventa"), default=precio_costo)
        if precio_costo <= 0:
            precio_costo = Decimal("0.01")
            incidents.add("WARN", "MIGRATE", table, key, "Precio costo <= 0; ajustado a 0.01")
        if precio_venta <= 0:
            incidents.add("WARN", "MIGRATE", table, key, "Precio venta inválido; fila omitida")
            c.omitted += 1
            continue

        stock = parse_decimal(row_value(row, "stock"), default=Decimal("0"))
        stock_minimo = parse_decimal(row_value(row, "aviso"), default=Decimal("5"))
        iva_pct = parse_decimal(row_value(row, "iva"), default=Decimal("0"))

        _, created = Producto.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "descripcion": row_value(row, "ubicacion"),
                "categoria": categoria,
                "proveedor": proveedor,
                "precio_costo": precio_costo,
                "precio_venta": precio_venta,
                "precio_venta_minimo": precio_venta,
                "stock": stock,
                "stock_minimo": stock_minimo if stock_minimo >= 0 else Decimal("0"),
                "unidad_medida": unit_choice(row_value(row, "um")),
                "iva_porcentaje": iva_pct,
                "iva_exento": iva_pct == 0,
                "aplica_descuento": True,
                "es_servicio": False,
            },
        )
        c.inserted += int(created)
        c.updated += int(not created)
    return c


def migrate_motos(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_motos_registradas"
    if not table_exists(table):
        incidents.add("WARN", "MIGRATE", table, "", "Tabla no existe; se omite")
        return c

    for row in iter_table_rows(table):
        placa = fit(normalize_code(row_value(row, "moto")), 20)
        key = placa or f"row:{row.get('_source_row', '?')}"
        if not placa:
            incidents.add("WARN", "MIGRATE", table, key, "Moto sin placa")
            c.omitted += 1
            continue

        mecanico = None
        mecanico_nombre = fit(row_value(row, "mecanico"), 200)
        if mecanico_nombre:
            mecanico = Mecanico.objects.filter(nombre__iexact=mecanico_nombre).first()
            if not mecanico:
                incidents.add("WARN", "MIGRATE", table, key, f"Mecánico no resuelto: {mecanico_nombre}")

        _, created = Moto.objects.update_or_create(
            placa=placa,
            defaults={
                "marca": fit(row_value(row, "marca") or "NO ESPECIFICADA", 100),
                "modelo": fit("", 100),
                "color": fit("", 50),
                "anio": None,
                "cliente": None,
                "mecanico": mecanico,
                "proveedor": None,
                "fecha_ingreso": parse_date(row_value(row, "fecha")),
                "observaciones": "Migrado desde legacy",
            },
        )
        c.inserted += int(created)
        c.updated += int(not created)
    return c


def migrate_usuarios_conservador(incidents: IncidentLogger) -> Counter:
    c = Counter()
    table = "staging_dbo_usuarios"
    if not table_exists(table):
        return c
    for row in iter_table_rows(table):
        username = fit(normalize_string(row_value(row, "usuario"), upper=False), 150)
        if not username:
            c.omitted += 1
            continue
        if maybe_get_user(username):
            c.updated += 1
            continue
        # Conservador: no activar password legacy plano.
        Usuario.objects.create(
            username=username,
            first_name=fit(row_value(row, "nombre"), 150),
            is_active=False,
            tipo_usuario="VENDEDOR",
        )
        c.inserted += 1
        incidents.add("INFO", "MIGRATE", table, username, "Usuario creado inactivo; password legacy no migrado")
    return c


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    dry_run = (not args.commit) or args.dry_run
    setup_django()

    incidents = IncidentLogger()
    results: dict[str, Counter] = defaultdict(Counter)

    with transaction.atomic():
        results["categorias"] = migrate_categorias(incidents)
        results["impuestos"] = migrate_impuestos(incidents)
        results["configuracion_empresa"] = migrate_empresa(incidents)

        contacto_res = migrate_contactos(incidents)
        results["clientes"] = contacto_res["clientes"]
        results["proveedores"] = contacto_res["proveedores"]

        results["mecanicos"] = migrate_mecanicos(incidents)
        results["productos"] = migrate_productos(incidents)
        results["motos"] = migrate_motos(incidents)
        results["usuarios"] = migrate_usuarios_conservador(incidents)

        # Tablas deliberadamente NO migradas de forma directa.
        incidents.add("INFO", "MIGRATE", "staging_dbo_prefactura", "", "No migrada por falta de correspondencia determinística")
        incidents.add("INFO", "MIGRATE", "staging_dbo_ivas", "", "No migrada (uso analítico/conciliación)")
        incidents.add("INFO", "MIGRATE", "staging_dbo_ivas_r", "", "No migrada (uso analítico/conciliación)")
        incidents.add("INFO", "MIGRATE", "staging_dbo_numeracion_fac", "", "No migrada a DIAN/Factus por criterio conservador")

        for name, c in results.items():
            LOGGER.info("%s: insertados=%s actualizados=%s omitidos=%s", name, c.inserted, c.updated, c.omitted)

        incidents.dump_json(args.incidents_json)

        if dry_run:
            LOGGER.warning("Dry-run activo: rollback")
            transaction.set_rollback(True)


if __name__ == "__main__":
    main()
