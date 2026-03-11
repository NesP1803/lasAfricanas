from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('facturacion', '0002_unify_factura_electronica'),
        ('facturacion_electronica', '0002_catalogos_factus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notacreditoelectronica',
            name='factura',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notas_credito', to='facturacion.facturaelectronica', verbose_name='Factura electrónica'),
        ),
        migrations.DeleteModel(
            name='FacturaElectronica',
        ),
    ]
