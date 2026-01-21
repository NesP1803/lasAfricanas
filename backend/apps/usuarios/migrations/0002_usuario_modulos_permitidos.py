from django.db import migrations, models
import apps.usuarios.models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='modulos_permitidos',
            field=models.JSONField(default=apps.usuarios.models.default_modulos_permitidos, verbose_name='Módulos permitidos'),
        ),
    ]
