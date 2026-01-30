from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
        ('ventas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitudDescuento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')),
                ('descuento_solicitado', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='Descuento solicitado (%)')),
                ('descuento_aprobado', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Descuento aprobado (%)')),
                ('subtotal', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Subtotal')),
                ('iva', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='IVA')),
                ('total_antes_descuento', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Total antes de descuento')),
                ('total_con_descuento', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Total con descuento')),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('APROBADO', 'Aprobado'), ('RECHAZADO', 'Rechazado')], default='PENDIENTE', max_length=20, verbose_name='Estado')),
                ('aprobador', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='solicitudes_descuento_recibidas', to='usuarios.usuario', verbose_name='Aprobador')),
                ('vendedor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='solicitudes_descuento', to='usuarios.usuario', verbose_name='Vendedor')),
            ],
            options={
                'verbose_name': 'Solicitud de Descuento',
                'verbose_name_plural': 'Solicitudes de Descuento',
                'db_table': 'solicitudes_descuento',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='solicituddescuento',
            index=models.Index(fields=['vendedor'], name='solicitudes_vendedor_idx'),
        ),
        migrations.AddIndex(
            model_name='solicituddescuento',
            index=models.Index(fields=['aprobador'], name='solicitudes_aprobador_idx'),
        ),
        migrations.AddIndex(
            model_name='solicituddescuento',
            index=models.Index(fields=['estado'], name='solicitudes_estado_idx'),
        ),
    ]
