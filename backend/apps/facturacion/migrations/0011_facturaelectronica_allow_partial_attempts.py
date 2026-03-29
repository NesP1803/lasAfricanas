from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0010_rename_facturacion__environ_cf6ae4_idx_facturacion_environ_cd9daf_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facturaelectronica',
            name='cufe',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=128,
                null=True,
                unique=True,
                verbose_name='CUFE',
            ),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='uuid',
            field=models.CharField(blank=True, db_index=True, max_length=128, null=True, verbose_name='UUID'),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='number',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                null=True,
                verbose_name='Número de factura',
            ),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='reference_code',
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                unique=True,
                verbose_name='Código de referencia',
            ),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='xml_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL XML'),
        ),
        migrations.AlterField(
            model_name='facturaelectronica',
            name='pdf_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL PDF'),
        ),
    ]
