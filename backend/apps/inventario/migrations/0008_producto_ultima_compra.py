from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0007_merge_20260202_2124'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='ultima_compra',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Última compra'),
        ),
    ]
