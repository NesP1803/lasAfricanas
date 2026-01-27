from django.db import migrations


def create_default_templates(apps, schema_editor):
    Template = apps.get_model('plantillas', 'Template')
    TemplateVersion = apps.get_model('plantillas', 'TemplateVersion')

    default_html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
</head>
<body>
  <div class="document">
    <header class="header">
      <h1>{{ empresa.nombre }}</h1>
      <p>NIT: {{ empresa.nit }}</p>
      <p>{{ empresa.direccion }} · {{ empresa.ciudad }}</p>
      <p>Tel: {{ empresa.telefono }}</p>
    </header>

    <section class="doc-info">
      <div>
        <strong>{{ doc.tipo }}</strong>
        <div>No. {{ doc.numero }}</div>
        <div>{{ doc.fecha }} {{ doc.hora }}</div>
      </div>
      <div class="cliente">
        <strong>Cliente</strong>
        <div>{{ cliente.nombre }}</div>
        <div>NIT/CC: {{ cliente.nit }}</div>
        <div>{{ cliente.direccion }}</div>
        <div>{{ cliente.telefono }}</div>
      </div>
    </section>

    <table class="items">
      <thead>
        <tr>
          <th>Descripción</th>
          <th>Código</th>
          <th>Cant.</th>
          <th>V. Unit.</th>
          <th>Desc.</th>
          <th>IVA%</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr>
          <td>{{ item.descripcion }}</td>
          <td>{{ item.codigo }}</td>
          <td class="right">{{ item.cantidad }}</td>
          <td class="right">{{ item.valor_unitario }}</td>
          <td class="right">{{ item.descuento }}</td>
          <td class="right">{{ item.iva_pct }}</td>
          <td class="right">{{ item.total }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    <section class="totals">
      <div class="totals-box">
        <div><span>Subtotal</span><span>{{ totales.subtotal }}</span></div>
        <div><span>Descuentos</span><span>{{ totales.descuentos }}</span></div>
        <div><span>Impuestos</span><span>{{ totales.impuestos }}</span></div>
        <div class="total"><span>Total</span><span>{{ totales.total }}</span></div>
      </div>
      <div class="payment-box">
        <div><span>Recibido</span><span>{{ totales.recibido }}</span></div>
        <div><span>Cambio</span><span>{{ totales.cambio }}</span></div>
      </div>
    </section>

    <footer class="footer">
      <div class="line"></div>
      <p>{{ doc.observaciones }}</p>
      <p>{{ extras.mensaje }}</p>
    </footer>
  </div>
</body>
</html>
"""

    default_css = """
    @page { size: A4; margin: 18mm; }
    body { font-family: Arial, sans-serif; font-size: 11px; color: #111; }
    .header { text-align: center; margin-bottom: 16px; }
    .header h1 { margin: 0; font-size: 18px; letter-spacing: 1px; }
    .doc-info { display: flex; justify-content: space-between; margin-bottom: 16px; }
    .doc-info .cliente { text-align: right; }
    .items { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
    .items th { background: #f2f2f2; padding: 6px; border-bottom: 1px solid #ccc; }
    .items td { padding: 6px; border-bottom: 1px solid #e1e1e1; }
    .items .right { text-align: right; }
    .totals { display: flex; justify-content: flex-end; gap: 16px; }
    .totals-box, .payment-box { border: 1px solid #ccc; padding: 8px 12px; min-width: 180px; }
    .totals-box div, .payment-box div { display: flex; justify-content: space-between; padding: 2px 0; }
    .totals-box .total { font-weight: bold; font-size: 12px; }
    .footer { margin-top: 24px; text-align: center; font-size: 10px; }
    .line { border-top: 1px solid #ccc; margin-bottom: 8px; }
    """

    receipt_text = """
[CENTER]{{ empresa.nombre }}
[CENTER]NIT: {{ empresa.nit }}
[CENTER]{{ empresa.direccion }} - {{ empresa.ciudad }}
[CENTER]TEL: {{ empresa.telefono }}
[LINE]
[CENTER]{{ doc.tipo }} No {{ doc.numero }}
[CENTER]{{ doc.fecha }} {{ doc.hora }}
[LINE]
Cliente: {{ cliente.nombre }}
NIT/CC: {{ cliente.nit }}
{{ cliente.direccion }}
{{ cliente.telefono }}
[LINE]
{% for item in items %}
{{ item.descripcion }}
[RIGHT]{{ item.cantidad }} x {{ item.valor_unitario }} = {{ item.total }}
{% endfor %}
[LINE]
[RIGHT]SUBTOTAL: {{ totales.subtotal }}
[RIGHT]DESCUENTO: {{ totales.descuentos }}
[RIGHT]IMPUESTOS: {{ totales.impuestos }}
[RIGHT][B]TOTAL: {{ totales.total }}[/B]
[LINE]
[RIGHT]RECIBIDO: {{ totales.recibido }}
[RIGHT]CAMBIO: {{ totales.cambio }}
[LINE]
[CENTER]{{ extras.mensaje }}
[CUT]
"""

    document_types = [
        ('QUOTATION', 'Cotización'),
        ('INVOICE', 'Factura de venta'),
        ('DELIVERY_NOTE', 'Remisión'),
        ('CREDIT_NOTE', 'Nota crédito'),
    ]

    for doc_type, label in document_types:
        pdf_template = Template.objects.create(
            name=f"{label} - PDF estándar",
            document_type=doc_type,
            output_type='PDF',
            is_active=True,
        )
        pdf_version = TemplateVersion.objects.create(
            template=pdf_template,
            version_number=1,
            html=default_html,
            css=default_css,
            receipt_text=None,
            comment="Plantilla inicial",
        )
        pdf_template.current_version = pdf_version
        pdf_template.save(update_fields=['current_version'])

        receipt_template = Template.objects.create(
            name=f"{label} - Tirilla estándar",
            document_type=doc_type,
            output_type='RECEIPT',
            is_active=True,
        )
        receipt_version = TemplateVersion.objects.create(
            template=receipt_template,
            version_number=1,
            html=None,
            css=None,
            receipt_text=receipt_text,
            comment="Plantilla inicial",
        )
        receipt_template.current_version = receipt_version
        receipt_template.save(update_fields=['current_version'])


class Migration(migrations.Migration):

    dependencies = [
        ('plantillas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_templates, migrations.RunPython.noop),
    ]
