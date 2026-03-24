from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0008_rangonumeraciondian_configuraciondian'),
    ]

    operations = [
        migrations.AddField(
            model_name='rangonumeraciondian',
            name='document_code',
            field=models.CharField(
                choices=[('FACTURA_VENTA', 'Factura de venta')],
                db_index=True,
                default='FACTURA_VENTA',
                max_length=30,
                verbose_name='Tipo de documento',
            ),
        ),
        migrations.AddField(
            model_name='rangonumeraciondian',
            name='environment',
            field=models.CharField(
                choices=[('SANDBOX', 'Sandbox'), ('PRODUCTION', 'Producción')],
                db_index=True,
                default='SANDBOX',
                max_length=20,
                verbose_name='Entorno',
            ),
        ),
        migrations.AddField(
            model_name='rangonumeraciondian',
            name='factus_range_id',
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True, verbose_name='ID de rango en Factus'),
        ),
        migrations.AddField(
            model_name='rangonumeraciondian',
            name='is_active_remote',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Activo remoto en Factus'),
        ),
        migrations.AddField(
            model_name='rangonumeraciondian',
            name='is_selected_local',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Seleccionado localmente para facturar'),
        ),
        migrations.AddIndex(
            model_name='rangonumeraciondian',
            index=models.Index(fields=['environment', 'document_code', 'is_active_remote'], name='facturacion__environ_cf6ae4_idx'),
        ),
        migrations.AddIndex(
            model_name='rangonumeraciondian',
            index=models.Index(fields=['environment', 'document_code', 'is_selected_local'], name='facturacion__environ_cf4f41_idx'),
        ),
    ]
