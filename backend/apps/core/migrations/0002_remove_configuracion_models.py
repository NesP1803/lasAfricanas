from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Auditoria',
        ),
        migrations.DeleteModel(
            name='ConfiguracionEmpresa',
        ),
        migrations.DeleteModel(
            name='ConfiguracionFacturacion',
        ),
        migrations.DeleteModel(
            name='Impuesto',
        ),
    ]
