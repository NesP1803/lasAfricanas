from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0011_facturaelectronica_allow_partial_attempts'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturaelectronica',
            name='correo_enviado',
            field=models.BooleanField(default=False, verbose_name='Correo enviado por Factus'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='correo_enviado_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha envío de correo'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='pdf_uploaded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha carga PDF en Factus'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='pdf_uploaded_to_factus',
            field=models.BooleanField(default=False, verbose_name='PDF personalizado cargado en Factus'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='public_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL pública'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='qr_data',
            field=models.TextField(blank=True, null=True, verbose_name='Contenido QR'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='qr_image_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL imagen QR remota'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='ultimo_error_correo',
            field=models.TextField(blank=True, null=True, verbose_name='Último error de correo'),
        ),
        migrations.AddField(
            model_name='facturaelectronica',
            name='ultimo_error_pdf',
            field=models.TextField(blank=True, null=True, verbose_name='Último error PDF'),
        ),
    ]
