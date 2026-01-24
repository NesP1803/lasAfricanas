from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Auditoria, AuditoriaArchivo


class Command(BaseCommand):
    help = (
        "Archiva registros de auditoría antiguos y elimina el histórico "
        "que excede la retención configurada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Cantidad de registros por lote para archivado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra cuántos registros se moverían sin modificar datos.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        retention_days = getattr(settings, "AUDITORIA_RETENTION_DAYS", 365)
        archive_retention_days = getattr(
            settings, "AUDITORIA_ARCHIVE_RETENTION_DAYS", 3650
        )

        now = timezone.now()
        cutoff = now - timedelta(days=retention_days)
        archive_cutoff = now - timedelta(days=archive_retention_days)

        qs = Auditoria.objects.filter(fecha_hora__lt=cutoff).order_by("fecha_hora")
        total_to_archive = qs.count()

        self.stdout.write(
            self.style.NOTICE(
                f"Registros a archivar: {total_to_archive} (antes de {cutoff:%Y-%m-%d})"
            )
        )

        if not dry_run and total_to_archive:
            archived_count = 0
            batch = []
            ids = []
            for registro in qs.iterator(chunk_size=batch_size):
                batch.append(
                    AuditoriaArchivo(
                        fecha_hora=registro.fecha_hora,
                        usuario=registro.usuario,
                        usuario_nombre=registro.usuario_nombre,
                        accion=registro.accion,
                        modelo=registro.modelo,
                        objeto_id=registro.objeto_id,
                        notas=registro.notas,
                        ip_address=registro.ip_address,
                    )
                )
                ids.append(registro.id)
                if len(batch) >= batch_size:
                    archived_count += self._flush(batch, ids)
                    batch, ids = [], []
            if batch:
                archived_count += self._flush(batch, ids)
            self.stdout.write(self.style.SUCCESS(f"Archivados: {archived_count}"))

        purged_count = 0
        if archive_retention_days > 0:
            purge_qs = AuditoriaArchivo.objects.filter(fecha_hora__lt=archive_cutoff)
            self.stdout.write(
                self.style.NOTICE(
                    "Registros en archivo a eliminar: "
                    f"{purge_qs.count()} (antes de {archive_cutoff:%Y-%m-%d})"
                )
            )
            if not dry_run:
                purged_count, _ = purge_qs.delete()
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Eliminados del archivo: {purged_count}"))

    @staticmethod
    def _flush(batch, ids):
        with transaction.atomic():
            AuditoriaArchivo.objects.bulk_create(batch)
            deleted, _ = Auditoria.objects.filter(id__in=ids).delete()
        return deleted
