from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0002_decimal_cantidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='moto',
            name='fecha_ingreso',
            field=models.DateField(blank=True, null=True),
        ),
    ]
