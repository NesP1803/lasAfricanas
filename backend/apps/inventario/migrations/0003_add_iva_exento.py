from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventario', '0002_allow_null_proveedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='iva_exento',
            field=models.BooleanField(default=False, verbose_name='IVA exento'),
        ),
    ]
