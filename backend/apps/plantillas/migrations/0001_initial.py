from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('document_type', models.CharField(choices=[('QUOTATION', 'Cotización'), ('INVOICE', 'Factura de venta'), ('DELIVERY_NOTE', 'Remisión'), ('CREDIT_NOTE', 'Nota crédito'), ('DEBIT_NOTE', 'Nota débito')], max_length=30)),
                ('output_type', models.CharField(choices=[('PDF', 'PDF'), ('RECEIPT', 'Tirilla')], max_length=20)),
                ('is_active', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Plantilla de documento',
                'verbose_name_plural': 'Plantillas de documentos',
                'db_table': 'document_templates',
            },
        ),
        migrations.CreateModel(
            name='TemplateVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField()),
                ('html', models.TextField(blank=True, null=True)),
                ('css', models.TextField(blank=True, null=True)),
                ('receipt_text', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('comment', models.CharField(blank=True, max_length=255)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='template_versions', to=settings.AUTH_USER_MODEL)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='plantillas.template')),
            ],
            options={
                'verbose_name': 'Versión de plantilla',
                'verbose_name_plural': 'Versiones de plantillas',
                'ordering': ['-version_number'],
                'db_table': 'document_template_versions',
                'unique_together': {('template', 'version_number')},
            },
        ),
        migrations.AddField(
            model_name='template',
            name='current_version',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='plantillas.templateversion'),
        ),
        migrations.AddIndex(
            model_name='template',
            index=models.Index(fields=['document_type', 'output_type', 'is_active'], name='document_t_document_23d6fe_idx'),
        ),
    ]
