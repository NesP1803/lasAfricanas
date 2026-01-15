from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_remove_plantillas_facturacion"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionModulos",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("configuracion_enabled", models.BooleanField(default=True)),
                ("registrar_enabled", models.BooleanField(default=True)),
                ("listados_enabled", models.BooleanField(default=True)),
                ("articulos_enabled", models.BooleanField(default=True)),
                ("taller_enabled", models.BooleanField(default=True)),
                ("facturacion_enabled", models.BooleanField(default=True)),
                ("reportes_enabled", models.BooleanField(default=True)),
                (
                    "configuracion",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accesos_modulos",
                        to="core.configuracionempresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuración de Módulos",
                "verbose_name_plural": "Configuración de Módulos",
                "db_table": "configuracion_modulos",
            },
        ),
    ]
