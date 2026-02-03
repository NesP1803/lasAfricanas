from django.db import migrations, models
import decimal
from django.core.validators import MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordenrepuesto',
            name='cantidad',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[MinValueValidator(decimal.Decimal('0.01'))],
            ),
        ),
    ]
