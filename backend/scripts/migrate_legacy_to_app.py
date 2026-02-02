#!/usr/bin/env python
"""
Migrate legacy staging tables (legacy_*) into Django app tables.

Cambios clave:
- Cruce correcto FACTURAS/REMISIONES con DETALLES usando:  prefijo + nofactura  (ej: "FAC-5000")
- Soporta DRY-RUN real (rollback al final)
- Evita duplicados por defecto (tablas *1). Puedes activarlos con --include-duplicates
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, Optional

import django
from django.contrib.auth import get_user_model
from django.db import connection, transaction

LOGGER = logging.getLogger(__name__)

Categoria = None
Cliente = None
DetalleVenta = None
Impuesto = None
Mecanico = None
Moto = None
Producto = None
Proveedor = None
Venta = None
VentaAnulada = None


def setup_django() -> None:
    global Categoria, Cliente, DetalleVenta, Impuesto, Mecanico, Moto, Producto, Proveedor, Venta, VentaAnulada
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from apps.core.models import Impuesto as ImpuestoModel
    from apps.inventario.models import Categoria as CategoriaModel, Producto as ProductoModel, Proveedor as ProveedorModel
    from apps.taller.models import Moto as MotoModel, Mecanico as MecanicoModel
    from apps.ventas.models import (
        Cliente as ClienteModel,
        DetalleVenta as DetalleVentaModel,
        Venta as VentaModel,
        VentaAnulada as VentaAnuladaModel,
    )

    Categoria = CategoriaModel
    Cliente = ClienteModel
    DetalleVenta = DetalleVentaModel
    Impuesto = ImpuestoModel
    Mecanico = MecanicoModel
    Moto = MotoModel
    Producto = ProductoModel
    Proveedor = ProveedorModel
    Venta = VentaModel
    VentaAnulada = VentaAnuladaModel


def normalize_field(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def build_row_map(row: Dict[str, object]) -> Dict[str, object]:
    return {normalize_field(key): value for key, value in row.items()}


def value_from_row(row_map: Dict[str, object], candidates: Iterable[str], default: str = "") -> str:
    for candidate in candidates:
        key = normalize_field(candidate)
        if key in row_map and row_map[key] not in (None, ""):
            return str(row_map[key]).strip()
    return default


def to_decimal(value: str, default: Decimal = Decimal("0")) -> Decimal:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return default


def to_int(value: str, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(str(value).replace(",", ".")))
    except ValueError:
        return default


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


def iter_table_rows(table: str, batch: int = 500) -> Iterable[Dict[str, object]]:
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {quote(table)}")
        columns = [col[0] for col in cursor.description]
        while True:
            rows = cursor.fetchmany(batch)
            if not rows:
                break
            for row in rows:
                yield dict(zip(columns, row))


def get_default_categoria() -> "Categoria":
    categoria, _ = Categoria.objects.get_or_create(
        nombre="Sin categoría",
        defaults={"descripcion": "Categoría por defecto para legacy", "orden": 0},
    )
    return categoria


def get_default_proveedor() -> "Proveedor":
    proveedor, _ = Proveedor.objects.get_or_create(
        nombre="Proveedor Legacy",
        defaults={"nit": "", "telefono": "", "email": ""},
    )
    return proveedor


def get_default_cliente() -> "Cliente":
    cliente, _ = Cliente.objects.get_or_create(
        numero_documento="0000000",
        defaults={
            "tipo_documento": "CC",
            "nombre": "Cliente Legacy",
            "telefono": "",
            "email": "",
            "direccion": "",
            "ciudad": "",
        },
    )
    return cliente


def get_admin_user():
    User = get_user_model()
    return User.objects.filter(username="admin").first()


def find_user(value: str):
    User = get_user_model()
    if not value:
        return get_admin_user()
    user = User.objects.filter(username__iexact=value).first()
    if user:
        return user
    parts = value.split()
    if parts:
        user = User.objects.filter(first_name__iexact=parts[0]).first()
        if user:
            return user
    return get_admin_user()


def import_categorias(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    created = 0
    for row in iter_table_rows(table):
        row_map = build_row_map(row)
        nombre = value_from_row(row_map, ["categoria", "nombre", "descripcion"]).strip()
        if not nombre:
            continue
        _, was_created = Categoria.objects.get_or_create(
            nombre=nombre,
            defaults={"descripcion": value_from_row(row_map, ["detalle", "observacion", "descripcion"]), "orden": 0},
        )
        created += int(was_created)
    LOGGER.info("Categorias importadas desde %s: %s", table, created)
    return created


def import_impuestos(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    created = 0
    for row in iter_table_rows(table):
        row_map = build_row_map(row)
        nombre = value_from_row(row_map, ["impuesto", "nombre", "descripcion"]).strip()
        if not nombre:
            continue
        valor = value_from_row(row_map, ["valor", "codigo", "sigla"], default=nombre)
        porcentaje = to_decimal(value_from_row(row_map, ["porcentaje", "iva", "tasa"], default="0"))
        _, was_created = Impuesto.objects.get_or_create(
            nombre=nombre,
            defaults={"valor": valor, "porcentaje": porcentaje, "es_exento": porcentaje == 0},
        )
        created += int(was_created)
    LOGGER.info("Impuestos importados desde %s: %s", table, created)
    return created


def import_clientes(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    created = 0
    for index, row in enumerate(iter_table_rows(table), start=1):
        row_map = build_row_map(row)
        numero_documento = value_from_row(
            row_map,
            ["documento", "cedula", "nit", "numero_documento", "identificacion", "idcliente", "clienteid"],
            default=f"LEGACY-{table}-{index}",
        )
        nombre = value_from_row(row_map, ["nombre", "razon_social", "cliente"], default="Cliente Legacy")
        tipo_documento = value_from_row(row_map, ["tipo_documento", "tipo"], default="CC")
        telefono = value_from_row(row_map, ["telefono", "celular", "movil"])
        email = value_from_row(row_map, ["email", "correo"])
        direccion = value_from_row(row_map, ["direccion", "domicilio"])
        ciudad = value_from_row(row_map, ["ciudad", "municipio"])

        _, was_created = Cliente.objects.get_or_create(
            numero_documento=numero_documento,
            defaults={
                "tipo_documento": tipo_documento if tipo_documento else "CC",
                "nombre": nombre,
                "telefono": telefono,
                "email": email,
                "direccion": direccion,
                "ciudad": ciudad,
            },
        )
        created += int(was_created)

    LOGGER.info("Clientes importados desde %s: %s", table, created)
    return created


def import_usuarios(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    User = get_user_model()
    created = 0
    for row in iter_table_rows(table):
        row_map = build_row_map(row)
        username = value_from_row(row_map, ["usuario", "login", "username", "nombre"])
        if not username:
            continue
        # Respetar admin existente
        if username.lower() == "admin":
            continue

        email = value_from_row(row_map, ["email", "correo"])
        first_name = value_from_row(row_map, ["nombres", "nombre"], default="")
        last_name = value_from_row(row_map, ["apellidos", "apellido"], default="")
        tipo = value_from_row(row_map, ["tipo", "rol", "cargo"], default="VENDEDOR")

        user, was_created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "tipo_usuario": tipo if tipo else "VENDEDOR",
            },
        )
        if was_created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        created += int(was_created)

    LOGGER.info("Usuarios importados desde %s: %s", table, created)
    return created


def import_mecanicos(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    created = 0
    for row in iter_table_rows(table):
        row_map = build_row_map(row)
        nombre = value_from_row(row_map, ["nombre", "mecanico", "empleado"])
        if not nombre:
            continue
        telefono = value_from_row(row_map, ["telefono", "celular"])
        email = value_from_row(row_map, ["email", "correo"])
        direccion = value_from_row(row_map, ["direccion", "domicilio"])
        ciudad = value_from_row(row_map, ["ciudad", "municipio"])
        _, was_created = Mecanico.objects.get_or_create(
            nombre=nombre,
            defaults={
                "telefono": telefono,
                "email": email,
                "direccion": direccion,
                "ciudad": ciudad,
            },
        )
        created += int(was_created)

    LOGGER.info("Mecánicos importados desde %s: %s", table, created)
    return created


def import_productos(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    created = 0
    default_categoria = get_default_categoria()
    default_proveedor = get_default_proveedor()

    for row in iter_table_rows(table):
        row_map = build_row_map(row)
        codigo = value_from_row(row_map, ["codigo", "sku", "referencia", "id", "cod"])
        nombre = value_from_row(row_map, ["nombre", "descripcion", "articulo"])
        if not codigo or not nombre:
            continue

        categoria_nombre = value_from_row(row_map, ["categoria", "linea", "grupo"], default="")
        categoria = default_categoria
        if categoria_nombre:
            categoria, _ = Categoria.objects.get_or_create(
                nombre=categoria_nombre,
                defaults={"descripcion": "", "orden": 0},
            )

        proveedor_nombre = value_from_row(row_map, ["proveedor", "marca", "fabricante"], default="")
        proveedor = default_proveedor
        if proveedor_nombre:
            proveedor, _ = Proveedor.objects.get_or_create(nombre=proveedor_nombre)

        precio_costo = to_decimal(value_from_row(row_map, ["costo", "precio_costo", "precio_compra"], default="1"), Decimal("1"))
        precio_venta = to_decimal(value_from_row(row_map, ["precio", "precio_venta", "valor", "precioventa"], default="1"), Decimal("1"))
        stock = to_int(value_from_row(row_map, ["stock", "existencias", "cantidad"], default="0"))
        iva = to_decimal(value_from_row(row_map, ["iva", "porcentaje"], default="19"), Decimal("19"))
        precio_venta_minimo = to_decimal(
            value_from_row(row_map, ["precio_minimo", "precio_venta_minimo"], default=str(precio_venta)),
            precio_venta,
        )

        _, was_created = Producto.objects.get_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "descripcion": value_from_row(row_map, ["detalle", "observacion"], default=""),
                "categoria": categoria,
                "proveedor": proveedor,
                "precio_costo": precio_costo,
                "precio_venta": precio_venta,
                "precio_venta_minimo": precio_venta_minimo,
                "stock": stock,
                "stock_minimo": 5,
                "unidad_medida": value_from_row(row_map, ["unidad", "unidad_medida", "um"], default="UND"),
                "iva_porcentaje": iva,
                "aplica_descuento": True,
                "es_servicio": False,
            },
        )
        created += int(was_created)

    LOGGER.info("Productos importados desde %s: %s", table, created)
    return created


def import_motos(table: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0
    created = 0
    for row in iter_table_rows(table):
        row_map = build_row_map(row)
        placa = value_from_row(row_map, ["moto", "placa", "matricula"])
        if not placa:
            continue
        marca = value_from_row(row_map, ["marca"], default="")
        modelo = value_from_row(row_map, ["modelo"], default="")
        color = value_from_row(row_map, ["color"], default="")

        cliente_doc = value_from_row(row_map, ["documento", "cedula", "nit", "idcliente", "cliente"], default="")
        cliente = None
        if cliente_doc:
            cliente = Cliente.objects.filter(numero_documento=cliente_doc).first()

        mecanico_nombre = value_from_row(row_map, ["mecanico"], default="")
        mecanico = None
        if mecanico_nombre:
            mecanico = Mecanico.objects.filter(nombre__iexact=mecanico_nombre).first()

        _, was_created = Moto.objects.get_or_create(
            placa=placa,
            defaults={
                "marca": marca,
                "modelo": modelo,
                "color": color,
                "anio": None,
                "cliente": cliente,
                "mecanico": mecanico,
                "proveedor": None,
                "observaciones": value_from_row(row_map, ["observaciones", "nota"], default=""),
            },
        )
        created += int(was_created)

    LOGGER.info("Motos importadas desde %s: %s", table, created)
    return created


def get_cliente_from_row(row_map: Dict[str, object]) -> "Cliente":
    doc = value_from_row(row_map, ["documento", "cedula", "nit", "idcliente", "cliente"], default="")
    if doc:
        cliente = Cliente.objects.filter(numero_documento=doc).first()
        if cliente:
            return cliente

    nombre = value_from_row(row_map, ["cliente", "nombre", "razon_social"], default="")
    if nombre:
        cliente = Cliente.objects.filter(nombre__iexact=nombre).first()
        if cliente:
            return cliente

    return get_default_cliente()


def legacy_numero_comprobante(row_map: Dict[str, object], tipo_comprobante: str, index: int) -> str:
    """
    FACTURA: prefijo + nofactura -> FAC-5000
    REMISION: noremision/remision -> 1000
    COTIZACION: lo que venga
    """
    # FACTURAS
    if tipo_comprobante == "FACTURA":
        prefijo = value_from_row(row_map, ["prefijo"], default="").strip()
        nofactura = value_from_row(
            row_map,
            ["nofactura", "no_factura", "factura", "numero", "num", "numero_comprobante"],
            default="",
        ).strip()
        if nofactura:
            return f"{prefijo}-{nofactura}" if prefijo else nofactura

    # REMISIONES (cabecera trae noremision; detalles/anulaciones traen remision)
    if tipo_comprobante == "REMISION":
        noremision = value_from_row(
            row_map,
            ["noremision", "no_remision", "remision", "numero", "num", "numero_comprobante"],
            default="",
        ).strip()
        if noremision:
            return noremision

    # COTIZACION u otros
    numero = value_from_row(
        row_map,
        ["numero", "cotizacion", "num", "numero_comprobante"],
        default="",
    ).strip()
    return numero if numero else f"{tipo_comprobante}-{index}"


def import_ventas(table: str, tipo_comprobante: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0

    created = 0
    for index, row in enumerate(iter_table_rows(table), start=1):
        row_map = build_row_map(row)

        numero = legacy_numero_comprobante(row_map, tipo_comprobante, index)
        cliente = get_cliente_from_row(row_map)

        vendedor_nombre = value_from_row(row_map, ["vendedor", "usuario", "empleado"], default="")
        vendedor = find_user(vendedor_nombre)

        subtotal = to_decimal(value_from_row(row_map, ["subtotal"], default="0"))
        descuento_valor = to_decimal(value_from_row(row_map, ["descuento", "descuento_valor", "descuentos"], default="0"))
        iva = to_decimal(value_from_row(row_map, ["iva", "impuestos"], default="0"))
        total = to_decimal(value_from_row(row_map, ["total", "valor"], default=str(subtotal + iva - descuento_valor)))

        medio_pago = value_from_row(row_map, ["medio_pago", "mediopago", "pago", "forma_pago"], default="EFECTIVO")
        estado = value_from_row(row_map, ["estado"], default="FACTURADA")
        observaciones = value_from_row(row_map, ["observaciones", "nota"], default="")

        _, was_created = Venta.objects.get_or_create(
            numero_comprobante=numero,
            defaults={
                "tipo_comprobante": tipo_comprobante,
                "cliente": cliente,
                "vendedor": vendedor or get_admin_user(),
                "subtotal": subtotal,
                "descuento_valor": descuento_valor,
                "iva": iva,
                "total": total,
                "medio_pago": medio_pago,
                "estado": estado,
                "observaciones": observaciones,
                "descuento_porcentaje": Decimal("0"),
                "efectivo_recibido": total,
                "cambio": Decimal("0"),
            },
        )
        created += int(was_created)

    LOGGER.info("Ventas %s importadas desde %s: %s", tipo_comprobante, table, created)
    return created


def find_producto(row_map: Dict[str, object]) -> Optional["Producto"]:
    codigo = value_from_row(row_map, ["codigo", "sku", "referencia", "id"], default="")
    if codigo:
        producto = Producto.objects.filter(codigo=codigo).first()
        if producto:
            return producto

    nombre = value_from_row(row_map, ["producto", "nombre", "descripcion", "articulo"], default="")
    if nombre:
        return Producto.objects.filter(nombre__iexact=nombre).first()

    return None


def import_detalles(table: str, tipo_comprobante: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0

    created = 0
    for row in iter_table_rows(table):
        row_map = build_row_map(row)

        # Importante: detalles legacy suelen traer factura/remision como número (ej 5000) + prefijo FAC
        numero = legacy_numero_comprobante(row_map, tipo_comprobante, index=0).strip()
        if not numero:
            continue

        venta = Venta.objects.filter(numero_comprobante=numero, tipo_comprobante=tipo_comprobante).first()
        if not venta:
            continue

        producto = find_producto(row_map)
        if not producto:
            continue

        cantidad = to_int(value_from_row(row_map, ["cantidad", "cant"], default="1"), default=1)

        # en legacy tienes PrecioVenta / Pventa_u / PrecioU
        precio_unitario = to_decimal(
            value_from_row(row_map, ["precioventa", "pventau", "preciou", "precio", "valor", "precio_unitario"], default="1"),
            Decimal("1"),
        )

        descuento_unitario = to_decimal(value_from_row(row_map, ["descu_valor", "descuento", "descuento_unitario"], default="0"))
        iva_porcentaje = to_decimal(value_from_row(row_map, ["iva", "porcentaje"], default="19"), Decimal("19"))

        subtotal = precio_unitario * Decimal(cantidad)
        total = subtotal - (descuento_unitario * Decimal(cantidad))

        _, was_created = DetalleVenta.objects.get_or_create(
            venta=venta,
            producto=producto,
            defaults={
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "descuento_unitario": descuento_unitario,
                "iva_porcentaje": iva_porcentaje,
                "subtotal": subtotal,
                "total": total,
                "afecto_inventario": True,
            },
        )
        created += int(was_created)

    LOGGER.info("Detalles %s importados desde %s: %s", tipo_comprobante, table, created)
    return created


def import_anulaciones(table: str, tipo_comprobante: str) -> int:
    if not table_exists(table):
        LOGGER.warning("Tabla %s no existe", table)
        return 0

    created = 0
    admin_user = get_admin_user()

    for row in iter_table_rows(table):
        row_map = build_row_map(row)

        numero = legacy_numero_comprobante(
            row_map,
            tipo_comprobante=tipo_comprobante,
            index=0,
        ).strip()

        if not numero:
            continue

        venta = Venta.objects.filter(
            numero_comprobante=numero,
            tipo_comprobante=tipo_comprobante,
        ).first()

        if not venta:
            continue

        # En anulaciones de remisiones tu excel usa "causa"
        motivo = value_from_row(row_map, ["motivo", "razon", "causa"], default="OTRO")
        descripcion = value_from_row(row_map, ["descripcion", "detalle", "observacion", "causa"], default="Anulación legacy")

        _, was_created = VentaAnulada.objects.get_or_create(
            venta=venta,
            defaults={
                "motivo": motivo if motivo in dict(VentaAnulada.MOTIVO_CHOICES) else "OTRO",
                "descripcion": descripcion,
                "anulado_por": admin_user,
                "devuelve_inventario": True,
            },
        )
        created += int(was_created)

    LOGGER.info("Anulaciones %s importadas desde %s: %s", tipo_comprobante, table, created)
    return created



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="Aplica cambios en la base de datos")
    parser.add_argument("--dry-run", action="store_true", help="Simula la migración (default)")
    parser.add_argument(
        "--include-duplicates",
        action="store_true",
        help="Incluye tablas duplicadas (*1). Por defecto se omiten para evitar duplicados.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()
    dry_run = not args.commit or args.dry_run

    setup_django()

    include_dupes = bool(args.include_duplicates)

    maestros_actions = [
        ("legacy_dbo_usuarios", import_usuarios),
        ("legacy_dbo_vendedores", import_usuarios),
        ("legacy_dbo_empleados", import_mecanicos),

        ("legacy_dbo_contactos", import_clientes),
        ("legacy_migrarclientes", import_clientes),

        ("legacy_dbo_articulos", import_productos),

        ("legacy_dbo_motos_registradas", import_motos),
    ]

    documentos_actions = [
        ("legacy_dbo_facturas", lambda t: import_ventas(t, "FACTURA")),
        ("legacy_dbo_remisiones", lambda t: import_ventas(t, "REMISION")),
        ("legacy_dbo_cotizaciones", lambda t: import_ventas(t, "COTIZACION")),
    ]

    detalles_actions = [
        ("legacy_dbo_detallesfactura", lambda t: import_detalles(t, "FACTURA")),
        ("legacy_dbo_detallesremision", lambda t: import_detalles(t, "REMISION")),
    ]

    if include_dupes:
        maestros_actions += [
            ("legacy_dbo_contactos1", import_clientes),
            ("legacy_dbo_articulos1", import_productos),
        ]
        documentos_actions += [
            ("legacy_dbo_remisiones1", lambda t: import_ventas(t, "REMISION")),
        ]
        detalles_actions += [
            ("legacy_dbo_detallesremision1", lambda t: import_detalles(t, "REMISION")),
        ]

    steps = [
        (
            "catalogos",
            [
                ("legacy_dbo_impuestos", import_impuestos),
                ("legacy_dbo_ivas", import_impuestos),
                ("legacy_dbo_ivas_r", import_impuestos),
                ("legacy_dbo_categorias", import_categorias),
                ("legacy_dbo_categorias_fac", import_categorias),
                ("legacy_dbo_rem_categorias", import_categorias),
            ],
        ),
        ("maestros", maestros_actions),
        ("documentos", documentos_actions),
        ("detalles", detalles_actions),
        (
            "post_procesos",
            [
                ("legacy_dbo_anulaciones_facturas", lambda t: import_anulaciones(t, "FACTURA")),
                ("legacy_dbo_anulaciones_remisiones", lambda t: import_anulaciones(t, "REMISION")),
            ],
        ),
    ]

    LOGGER.info("Modo: %s", "COMMIT" if (args.commit and not args.dry_run) else "DRY-RUN")
    LOGGER.info("Include duplicates (*1): %s", "SI" if include_dupes else "NO")

    with transaction.atomic():
        for etapa, acciones in steps:
            LOGGER.info("==> Etapa %s", etapa)
            for table, func in acciones:
                func(table)

        if dry_run:
            LOGGER.warning("Dry-run activo: realizando rollback")
            transaction.set_rollback(True)


if __name__ == "__main__":
    main()
