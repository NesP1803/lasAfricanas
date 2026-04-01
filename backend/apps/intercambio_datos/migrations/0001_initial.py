from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('nombre', models.CharField(max_length=120, unique=True)),
                ('codigo', models.SlugField(max_length=120, unique=True)),
                ('entidades', models.JSONField(blank=True, default=list)),
                ('multihoja', models.BooleanField(default=True)),
            ],
            options={'db_table': 'intercambio_export_profile'},
        ),
        migrations.CreateModel(
            name='ImportProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('nombre', models.CharField(max_length=120, unique=True)),
                ('codigo', models.SlugField(max_length=120, unique=True)),
                ('precio_fuente', models.CharField(choices=[('FINAL', 'Precio final'), ('BASE_SIN_IVA', 'Precio base sin IVA')], default='FINAL', max_length=20)),
                ('activo', models.BooleanField(default=True)),
                ('configuracion', models.JSONField(blank=True, default=dict)),
            ],
            options={'db_table': 'intercambio_import_profile', 'ordering': ['nombre']},
        ),
        migrations.CreateModel(
            name='ExportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('GENERADO', 'Generado'), ('ERROR', 'Error')], default='PENDIENTE', max_length=20)),
                ('archivo', models.FileField(blank=True, null=True, upload_to='intercambio/exports/')),
                ('resumen', models.JSONField(blank=True, default=dict)),
                ('errores', models.JSONField(blank=True, default=list)),
                ('perfil', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='jobs', to='intercambio_datos.exportprofile')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='intercambio_export_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'intercambio_export_job', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ImportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('ANALIZADO', 'Analizado'), ('EJECUTADO', 'Ejecutado'), ('ERROR', 'Error')], default='PENDIENTE', max_length=20)),
                ('dry_run_hash', models.CharField(blank=True, max_length=64)),
                ('resumen', models.JSONField(blank=True, default=dict)),
                ('errores', models.JSONField(blank=True, default=list)),
                ('warnings', models.JSONField(blank=True, default=list)),
                ('perfil', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='jobs', to='intercambio_datos.importprofile')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='intercambio_import_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'intercambio_import_job', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ImportFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('nombre', models.CharField(max_length=255)),
                ('archivo', models.FileField(upload_to='intercambio/imports/')),
                ('extension', models.CharField(max_length=10)),
                ('checksum', models.CharField(db_index=True, max_length=64)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='intercambio_datos.importjob')),
            ],
            options={'db_table': 'intercambio_import_file'},
        ),
        migrations.CreateModel(
            name='ImportSheetAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('sheet_name', models.CharField(max_length=255)),
                ('entidad_detectada', models.CharField(blank=True, max_length=64)),
                ('confianza', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('estado', models.CharField(default='PENDIENTE', max_length=20)),
                ('mapping', models.JSONField(blank=True, default=dict)),
                ('resumen', models.JSONField(blank=True, default=dict)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sheets', to='intercambio_datos.importfile')),
            ],
            options={'db_table': 'intercambio_import_sheet_analysis'},
        ),
        migrations.CreateModel(
            name='ImportRowResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Activo')),
                ('row_number', models.PositiveIntegerField()),
                ('action', models.CharField(choices=[('INSERTADA', 'Insertada'), ('ACTUALIZADA', 'Actualizada'), ('OMITIDA', 'Omitida'), ('AMBIGUA', 'Ambigua'), ('ERROR', 'Error'), ('WARNING', 'Warning')], max_length=20)),
                ('natural_key', models.CharField(blank=True, max_length=255)),
                ('message', models.TextField(blank=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='row_results', to='intercambio_datos.importfile')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='row_results', to='intercambio_datos.importjob')),
                ('sheet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='row_results', to='intercambio_datos.importsheetanalysis')),
            ],
            options={'db_table': 'intercambio_import_row_result'},
        ),
        migrations.AddIndex(
            model_name='importrowresult',
            index=models.Index(fields=['job', 'action'], name='intercambio_i_job_id_35f9cb_idx'),
        ),
    ]
