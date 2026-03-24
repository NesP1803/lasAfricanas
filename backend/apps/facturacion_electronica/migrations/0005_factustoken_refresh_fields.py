from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion_electronica', '0004_alter_notacreditoelectronica_factura'),
    ]

    operations = [
        migrations.AddField(
            model_name='factustoken',
            name='refresh_expires_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Refresh expira en'),
        ),
        migrations.AddField(
            model_name='factustoken',
            name='refresh_expires_in',
            field=models.PositiveIntegerField(default=0, verbose_name='Refresh duración en segundos'),
        ),
        migrations.AddField(
            model_name='factustoken',
            name='refresh_token',
            field=models.TextField(blank=True, default='', verbose_name='Refresh token'),
        ),
    ]
