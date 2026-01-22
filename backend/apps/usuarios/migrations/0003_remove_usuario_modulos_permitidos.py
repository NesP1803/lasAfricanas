from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_usuario_modulos_permitidos'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='usuario',
            name='modulos_permitidos',
        ),
    ]
