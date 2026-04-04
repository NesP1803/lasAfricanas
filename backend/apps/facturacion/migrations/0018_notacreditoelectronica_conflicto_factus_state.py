from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0017_notacreditoelectronica_email_status_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notacreditoelectronica",
            name="estado_local",
            field=models.CharField(
                choices=[
                    ("BORRADOR", "Borrador"),
                    ("PENDIENTE_ENVIO", "Pendiente de envío"),
                    ("EN_PROCESO", "En proceso DIAN"),
                    ("CONFLICTO_FACTUS", "Conflicto Factus (sin confirmación remota)"),
                    ("ACEPTADA", "Aceptada"),
                    ("RECHAZADA", "Rechazada"),
                    ("ERROR_INTEGRACION", "Error de integración"),
                    ("ERROR_PERSISTENCIA", "Error de persistencia"),
                    ("ANULADA_LOCAL", "Anulada local"),
                    ("ELIMINADA_EN_FACTUS", "Eliminada en Factus"),
                ],
                db_index=True,
                default="BORRADOR",
                max_length=40,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="notacreditoelectronica",
            name="uq_nota_credito_abierta_factura_tipo",
        ),
        migrations.AddConstraint(
            model_name="notacreditoelectronica",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("estado_local__in", ["BORRADOR", "PENDIENTE_ENVIO", "EN_PROCESO", "CONFLICTO_FACTUS", "ACEPTADA"])
                ),
                fields=("factura", "tipo_nota"),
                name="uq_nota_credito_abierta_factura_tipo",
            ),
        ),
    ]
