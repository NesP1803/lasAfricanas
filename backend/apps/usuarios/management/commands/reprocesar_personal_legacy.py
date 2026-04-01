from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from apps.usuarios.models import PerfilVendedor, Usuario


@dataclass
class ImportCounter:
    creados: int = 0
    actualizados: int = 0
    omitidos: int = 0
    ambiguos: int = 0
    errores: int = 0


@dataclass
class ConsolidatedPerson:
    source_keys: set[str] = field(default_factory=set)
    username: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    telefono: str = ""
    sede: str = ""
    tipo_usuario: str = ""
    is_active: bool = True
    es_cajero: bool = False
    from_vendedores: bool = False
    ambiguous: bool = False
    ambiguous_reason: str = ""


def norm_str(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def norm_email(value: Any) -> str:
    email = norm_str(value).lower()
    return email if "@" in email else ""


def pick(row: dict[str, Any], *keys: str) -> str:
    lowered = {k.lower(): v for k, v in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return norm_str(value)
    return ""


def parse_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    raw = norm_str(value).lower()
    if raw in {"1", "true", "t", "si", "sí", "s", "y", "yes", "activo", "act", "x"}:
        return True
    if raw in {"0", "false", "f", "no", "n", "inactivo", "ina"}:
        return False
    return default


def split_name(full_name: str) -> tuple[str, str]:
    clean = norm_str(full_name)
    if not clean:
        return "", ""
    parts = clean.split(" ", 1)
    if len(parts) == 1:
        return parts[0][:150], ""
    return parts[0][:150], parts[1][:150]


def tipo_from_row(row: dict[str, Any]) -> str:
    raw = pick(row, "tipo_usuario", "tipo", "rol", "cargo", "perfil")
    value = raw.upper()
    if "ADMIN" in value:
        return "ADMIN"
    if "BOD" in value:
        return "BODEGUERO"
    if "MEC" in value:
        return "MECANICO"
    if "VEND" in value:
        return "VENDEDOR"
    return ""


class Command(BaseCommand):
    help = (
        "Reprocesa únicamente personal (usuarios) desde staging_dbo_usuarios, "
        "staging_dbo_vendedores y staging_dbo_empleados, con upsert idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simula cambios (rollback al final)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        counter = ImportCounter()
        self._resolved_tables: dict[str, tuple[str, str]] = {}

        with transaction.atomic():
            empleados_rows = self._read_table("staging_dbo_empleados")
            usuarios_rows = self._read_table("staging_dbo_usuarios")
            vendedores_rows = self._read_table("staging_dbo_vendedores")

            persons = self._consolidate_people(usuarios_rows, vendedores_rows, empleados_rows, counter)
            self._upsert_usuarios(persons, counter)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("Resumen reproceso de personal:"))
        self.stdout.write(f"  creados: {counter.creados}")
        self.stdout.write(f"  actualizados: {counter.actualizados}")
        self.stdout.write(f"  omitidos: {counter.omitidos}")
        self.stdout.write(f"  ambiguos: {counter.ambiguos}")
        self.stdout.write(f"  errores: {counter.errores}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run activo: se hizo rollback de todos los cambios."))

    def _read_table(self, table: str) -> list[dict[str, Any]]:
        resolved = self._resolve_table(table)
        if not resolved:
            self.stdout.write(self.style.WARNING(f"Tabla {table} no existe; se omite."))
            return []
        schema_name, table_name = resolved

        self.stdout.write(f"Usando tabla {schema_name}.{table_name} para '{table}'.")
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            qualified = f"{quote(schema_name)}.{quote(table_name)}"
            cursor.execute(f"SELECT * FROM {qualified}")
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _resolve_table(self, table: str) -> tuple[str, str] | None:
        if table in self._resolved_tables:
            return self._resolved_tables[table]

        normalized_target = table.lower()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND lower(table_name) = %s
                ORDER BY CASE WHEN table_schema='public' THEN 0 ELSE 1 END, table_schema, table_name
                """,
                [normalized_target],
            )
            matches = cursor.fetchall()

        if not matches:
            return None
        if len(matches) > 1:
            pretty = ", ".join(f"{schema}.{name}" for schema, name in matches)
            self.stdout.write(
                self.style.WARNING(
                    f"Tabla '{table}' encontrada en múltiples esquemas ({pretty}); se usa {matches[0][0]}.{matches[0][1]}"
                )
            )
        chosen = (matches[0][0], matches[0][1])
        self._resolved_tables[table] = chosen
        return chosen

    def _slug_username(self, value: str) -> str:
        raw = norm_str(value).lower()
        raw = unicodedata.normalize("NFKD", raw)
        raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
        raw = re.sub(r"[^a-z0-9]+", "_", raw)
        raw = re.sub(r"_+", "_", raw).strip("_")
        return raw[:150]

    def _build_fallback_username(self, person: ConsolidatedPerson, key: str) -> str:
        base = ""
        if person.username:
            base = self._slug_username(person.username)
        elif person.email:
            base = self._slug_username(person.email.split("@")[0])

        if not base:
            full_name = norm_str(f"{person.first_name} {person.last_name}")
            base = self._slug_username(full_name)

        if not base:
            base = self._slug_username(key.replace(":", "_"))

        if not base:
            base = "legacy_user"

        return base[:150]

    def _ensure_unique_username(self, base_username: str, exclude_pk: int | None = None) -> str:
        base = (base_username or "legacy_user").strip()[:150]
        candidate = base
        seq = 2

        while True:
            qs = Usuario.objects.filter(username__iexact=candidate)
            if exclude_pk:
                qs = qs.exclude(pk=exclude_pk)
            if not qs.exists():
                return candidate

            suffix = f"_{seq}"
            candidate = f"{base[:150 - len(suffix)]}{suffix}"
            seq += 1

    def _build_person_from_source(self, row: dict[str, Any], from_vendedor: bool = False) -> ConsolidatedPerson:
        username = pick(row, "username", "usuario", "login", "user")[:150]
        email = norm_email(pick(row, "email", "correo", "mail"))[:254]
        full_name = pick(row, "nombre_completo", "nombre", "vendedor", "empleado")
        first_name = pick(row, "first_name", "nombre1", "nombres")
        last_name = pick(row, "last_name", "apellido1", "apellidos")
        if not first_name and not last_name and full_name:
            first_name, last_name = split_name(full_name)

        tipo_usuario = "VENDEDOR" if from_vendedor else (tipo_from_row(row) or "VENDEDOR")
        if tipo_usuario == "MECANICO":
            tipo_usuario = ""

        person = ConsolidatedPerson(
            username=username,
            email=email,
            first_name=first_name[:150],
            last_name=last_name[:150],
            telefono=pick(row, "telefono", "celular", "tel")[:20],
            sede=pick(row, "sede", "sucursal")[:50],
            tipo_usuario=tipo_usuario,
            is_active=parse_bool(pick(row, "is_active", "activo", "estado"), default=True),
            es_cajero=parse_bool(pick(row, "es_cajero", "cajero"), default=False),
            from_vendedores=from_vendedor,
        )
        return person

    def _candidate_key(self, person: ConsolidatedPerson) -> str:
        if person.username:
            return f"username:{person.username.lower()}"
        if person.email:
            return f"email:{person.email.lower()}"
        name_key = norm_str(f"{person.first_name} {person.last_name}").lower()
        return f"name:{name_key}" if name_key else ""

    def _merge_person(self, base: ConsolidatedPerson, incoming: ConsolidatedPerson):
        for attr in ["username", "email", "first_name", "last_name", "telefono", "sede", "tipo_usuario"]:
            current = getattr(base, attr)
            value = getattr(incoming, attr)
            if value and not current:
                setattr(base, attr, value)
            elif value and current and value.lower() != current.lower():
                if attr in {"username", "email", "tipo_usuario"}:
                    base.ambiguous = True
                    base.ambiguous_reason = f"Conflicto en {attr}: '{current}' vs '{value}'"

        base.is_active = base.is_active or incoming.is_active
        base.es_cajero = base.es_cajero or incoming.es_cajero
        base.from_vendedores = base.from_vendedores or incoming.from_vendedores

    def _is_mecanico_row(self, row: dict[str, Any]) -> bool:
        marker = tipo_from_row(row)
        return marker == "MECANICO"

    def _consolidate_people(
        self,
        usuarios_rows: list[dict[str, Any]],
        vendedores_rows: list[dict[str, Any]],
        empleados_rows: list[dict[str, Any]],
        counter: ImportCounter,
    ) -> dict[str, ConsolidatedPerson]:
        consolidated: dict[str, ConsolidatedPerson] = {}
        empleados_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in empleados_rows:
            if self._is_mecanico_row(row):
                continue
            name = norm_str(pick(row, "empleado", "nombre", "vendedor", "nombre_completo")).lower()
            if name:
                empleados_by_name[name].append(row)

        for source, rows in (("usuarios", usuarios_rows), ("vendedores", vendedores_rows)):
            is_vendedor_src = source == "vendedores"
            for idx, row in enumerate(rows, start=1):
                person = self._build_person_from_source(row, from_vendedor=is_vendedor_src)
                key = self._candidate_key(person)
                if not key:
                    counter.ambiguos += 1
                    self.stdout.write(
                        self.style.WARNING(f"[{source}#{idx}] fila ambigua sin username/email/nombre: omitida")
                    )
                    continue

                name_key = norm_str(f"{person.first_name} {person.last_name}").lower()
                if name_key and name_key in empleados_by_name:
                    matches = empleados_by_name[name_key]
                    if len(matches) == 1:
                        empleado = matches[0]
                        if not person.telefono:
                            person.telefono = pick(empleado, "telefono", "celular", "tel")[:20]
                        if not person.sede:
                            person.sede = pick(empleado, "sede", "sucursal")[:50]
                        if not person.es_cajero:
                            person.es_cajero = parse_bool(pick(empleado, "es_cajero", "cajero"), default=False)
                    else:
                        person.ambiguous = True
                        person.ambiguous_reason = "Coincide con múltiples filas de empleados"

                if key not in consolidated:
                    consolidated[key] = person
                    continue

                self._merge_person(consolidated[key], person)

        return consolidated

    def _upsert_usuarios(self, persons: dict[str, ConsolidatedPerson], counter: ImportCounter) -> None:
        sede_values = {choice[0] for choice in Usuario.SEDE_CHOICES}

        for key, person in persons.items():
            if person.tipo_usuario == "MECANICO":
                counter.omitidos += 1
                self.stdout.write(self.style.WARNING(f"[{key}] marcado como MECANICO. Omitido por regla."))
                continue

            if person.ambiguous:
                self.stdout.write(
                    self.style.WARNING(
                        f"[{key}] ambiguo: {person.ambiguous_reason}. Se intentará crear/adaptar."
                    )
                )

            requested_username = person.username.strip()[:150] if person.username else ""
            if not requested_username:
                requested_username = self._build_fallback_username(person, key)
                self.stdout.write(
                    self.style.WARNING(
                        f"[{key}] sin username confiable. Se autogenera: {requested_username}"
                    )
                )
            else:
                requested_username = self._slug_username(requested_username) or self._build_fallback_username(person, key)

            existing_by_username = Usuario.objects.filter(username__iexact=requested_username).first()
            existing_by_email = Usuario.objects.filter(email__iexact=person.email).first() if person.email else None

            user = None

            if existing_by_username and existing_by_email and existing_by_username.pk == existing_by_email.pk:
                user = existing_by_username
            elif existing_by_username and existing_by_email and existing_by_username.pk != existing_by_email.pk:
                self.stdout.write(
                    self.style.WARNING(
                        f"[{key}] username/email apuntan a usuarios distintos. "
                        f"Se prioriza username='{existing_by_username.username}' y se ignora email conflictivo."
                    )
                )
                user = existing_by_username
                person.email = ""
            elif existing_by_username:
                user = existing_by_username
            elif existing_by_email:
                user = existing_by_email
                if user.username.lower() != requested_username.lower():
                    requested_username = self._ensure_unique_username(requested_username, exclude_pk=user.pk)
            else:
                requested_username = self._ensure_unique_username(requested_username)

            defaults = {
                "email": person.email,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "telefono": person.telefono,
                "sede": person.sede if person.sede in sede_values else "",
                "tipo_usuario": person.tipo_usuario or "VENDEDOR",
                "is_active": person.is_active,
                "es_cajero": person.es_cajero,
            }

            try:
                if user:
                    changed = False

                    if user.username != requested_username:
                        username_candidate = self._ensure_unique_username(requested_username, exclude_pk=user.pk)
                        if user.username != username_candidate:
                            user.username = username_candidate
                            changed = True

                    for field, value in defaults.items():
                        if getattr(user, field) != value:
                            setattr(user, field, value)
                            changed = True

                    if changed:
                        user.save(update_fields=["username", *defaults.keys()])
                        counter.actualizados += 1
                    else:
                        counter.omitidos += 1
                else:
                    user = Usuario(username=requested_username, **defaults)
                    user.set_unusable_password()
                    user.save()
                    counter.creados += 1

                if user.tipo_usuario == "VENDEDOR":
                    PerfilVendedor.objects.get_or_create(usuario=user)

            except Exception as exc:  # noqa: BLE001
                counter.errores += 1
                self.stdout.write(self.style.ERROR(f"[{key}] error al upsert: {exc}"))