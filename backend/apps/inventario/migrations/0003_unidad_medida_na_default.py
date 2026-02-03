from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0002_decimal_stock_cantidad'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='unidad_medida',
            field=models.CharField(
                choices=[
                    ('N/A', 'N/A'),
                    ('KG', 'Kilogramo'),
                    ('LT', 'Litro'),
                    ('MT', 'Metro'),
                ],
                default='N/A',
                help_text='N/A, KG, LT, MT',
                max_length=20,
                verbose_name='Unidad de medida',
            ),
        ),
    ]
