from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.services.legacy_excel_importer import LegacyExcelImporter


class Command(BaseCommand):
    help = (
        "Importa archivos XLSX legacy con clasificación automática por estructura y "
        "mapeo directo a tablas reales del sistema (sin staging por archivo)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--path", default="data", help="Directorio con archivos XLSX legacy.")
        parser.add_argument("--dry-run", action="store_true", help="Simular importación sin persistir cambios.")
        parser.add_argument("--commit", action="store_true", help="Persistir cambios en base de datos.")
        parser.add_argument(
            "--cleanup-temp-on-success",
            action="store_true",
            help="Eliminar tablas staging_* existentes solo si no hay errores críticos.",
        )

    def handle(self, *args, **options):
        commit = bool(options["commit"]) and not bool(options["dry_run"])
        base_path = Path(options["path"]).resolve()
        if not base_path.exists():
            raise CommandError(f"La ruta no existe: {base_path}")

        importer = LegacyExcelImporter(
            base_path=base_path,
            commit=commit,
            cleanup_temp_on_success=bool(options["cleanup_temp_on_success"]),
        )

        with transaction.atomic():
            payload = importer.run()
            if not commit:
                transaction.set_rollback(True)

        report_files = payload.get("report_files", [])
        self.stdout.write(self.style.SUCCESS(f"Archivos procesados: {len(payload.get('files', []))}"))
        self.stdout.write(self.style.SUCCESS(f"Datos no mapeados preservados: {len(payload.get('unmapped_payloads', []))}"))
        if report_files:
            self.stdout.write(self.style.NOTICE(f"Reportes: {report_files[0]} | {report_files[1]}"))
        self.stdout.write(self.style.WARNING("Modo DRY-RUN (rollback aplicado).") if not commit else self.style.SUCCESS("Modo COMMIT finalizado."))
