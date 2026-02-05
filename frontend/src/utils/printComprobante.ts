import type { ConfiguracionEmpresa } from '../types';

export type DocumentoDetalle = {
  descripcion: string;
  codigo?: string;
  cantidad: number;
  precioUnitario: number;
  descuento: number;
  ivaPorcentaje: number;
  total: number;
};

type DocumentoTipo = 'FACTURA' | 'REMISION' | 'COTIZACION';
export type DocumentoFormato = 'POS' | 'CARTA';

type PrintComprobanteParams = {
  formato?: DocumentoFormato;
  tipo: DocumentoTipo;
  numero: string;
  fecha: string;
  clienteNombre: string;
  clienteDocumento: string;
  medioPago?: string;
  estado?: string;
  detalles?: DocumentoDetalle[];
  subtotal: number;
  descuento: number;
  iva: number;
  total: number;
  efectivoRecibido?: number;
  cambio?: number;
  notas?: string;
  resolucion?: string;
  empresa?: ConfiguracionEmpresa | null;
};

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const formatFechaHora = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return fecha;
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const getEmpresaInfo = (empresa?: ConfiguracionEmpresa | null) => ({
  nombre: empresa?.razon_social || 'MOTOREPUESTOS LAS AFRICANAS',
  nit: empresa
    ? `${empresa.tipo_identificacion} ${empresa.identificacion}${empresa.dv ? `-${empresa.dv}` : ''}`
    : 'NIT 91.068.915-8',
  regimen: empresa?.regimen || 'Régimen común',
  direccion: empresa
    ? `${empresa.direccion}, ${empresa.ciudad}`
    : 'Calle 6 # 12A-45 Gaira, Santa Marta',
  telefono: empresa?.telefono || '',
});

const getTituloDocumento = (tipo: DocumentoTipo) =>
  tipo === 'COTIZACION' ? 'Cotización' : tipo === 'REMISION' ? 'Remisión' : 'Factura de venta';

export const printComprobante = ({
  formato = 'POS',
  tipo,
  numero,
  fecha,
  clienteNombre,
  clienteDocumento,
  medioPago,
  estado,
  detalles = [],
  subtotal,
  descuento,
  iva,
  total,
  efectivoRecibido,
  cambio,
  notas,
  resolucion,
  empresa,
}: PrintComprobanteParams) => {
  const printWindow = window.open('', '_blank', 'width=860,height=720');
  if (!printWindow) {
    return;
  }

  const infoEmpresa = getEmpresaInfo(empresa);
  const fechaFormateada = formatFechaHora(fecha);
  const tituloDocumento = getTituloDocumento(tipo);
  const detallesMostrar =
    detalles.length > 0
      ? detalles
      : [
          {
            descripcion: 'Detalle no disponible en el listado.',
            cantidad: 1,
            precioUnitario: total,
            descuento: 0,
            ivaPorcentaje: 0,
            total,
          },
        ];
  const detallesConIva = detallesMostrar.map((detalle) => {
    const base = detalle.cantidad * detalle.precioUnitario - detalle.descuento;
    const ivaDetalle = base * (detalle.ivaPorcentaje / 100);
    const totalDetalle = base + ivaDetalle;
    return {
      ...detalle,
      base,
      ivaDetalle,
      totalDetalle,
    };
  });
  const resumenIvaArray = Array.from(
    detallesConIva.reduce((acc, detalle) => {
      const item = acc.get(detalle.ivaPorcentaje) || { base: 0, iva: 0, total: 0 };
      acc.set(detalle.ivaPorcentaje, {
        base: item.base + detalle.base,
        iva: item.iva + detalle.ivaDetalle,
        total: item.total + detalle.totalDetalle,
      });
      return acc;
    }, new Map<number, { base: number; iva: number; total: number }>())
  ).map(([porcentaje, valores]) => ({
    porcentaje,
    ...valores,
  }));

  const estilos =
    formato === 'POS'
      ? `
    :root {
      --ticket-width: 80mm;
      --ticket-padding: 10px;
      --border-color: #cbd5e1;
      --muted: #64748b;
      --text: #0f172a;
    }
    * { box-sizing: border-box; }
    @page { size: var(--ticket-width) auto; margin: 0; }
    html, body { width: var(--ticket-width); margin: 0; padding: 0; }
    @media print {
      html, body { width: var(--ticket-width); }
      body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    }
    body {
      font-family: "Courier New", Courier, monospace;
      padding: 0;
      color: var(--text);
      font-size: 10px;
      line-height: 1.25;
      background: #fff;
    }
    .ticket {
      width: var(--ticket-width);
      margin: 0 auto;
      border: 1px solid var(--border-color);
      padding: var(--ticket-padding);
      background: #fff;
    }
    .center { text-align: center; }
    .title { font-size: 11px; text-transform: uppercase; margin: 6px 0 2px; }
    .subtitle { font-size: 10px; font-weight: 600; margin: 0; }
    .line { border-top: 1px dashed #94a3b8; margin: 6px 0; }
    .row { display: flex; justify-content: space-between; margin: 2px 0; }
    .label { color: var(--muted); font-size: 9px; }
    .value { font-weight: 600; }
    .detalle-title { display: flex; justify-content: space-between; font-weight: 600; margin-top: 6px; }
    .detalle-item { margin-top: 4px; }
    .detalle-desc { text-transform: uppercase; margin: 0 0 2px; }
    .detalle-meta { display: flex; justify-content: space-between; font-size: 9px; color: var(--muted); }
    .totals { margin-top: 6px; }
    .totals .row { font-size: 10px; }
    .totals .total { font-size: 11px; font-weight: 700; }
    .nota { margin-top: 6px; font-size: 9px; color: var(--muted); }
  `
      : `
    body { font-family: Arial, sans-serif; padding: 32px; color: #0f172a; font-size: 12px; }
    .sheet { max-width: 880px; margin: 0 auto; border: 1px solid #cbd5e1; padding: 24px; }
    .header { display: flex; justify-content: space-between; gap: 16px; }
    .header h1 { font-size: 14px; text-transform: uppercase; margin: 0 0 4px; }
    .header p { margin: 2px 0; color: #475569; }
    .doc-title { text-align: right; }
    .doc-title p { margin: 2px 0; }
    .doc-number { font-size: 18px; font-weight: 700; }
    .resolucion { margin-top: 8px; color: #64748b; font-size: 11px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
    .label { text-transform: uppercase; color: #64748b; font-size: 11px; }
    .section-title { font-weight: 600; margin-top: 2px; }
    .table { width: 100%; border: 1px solid #e2e8f0; border-collapse: collapse; margin-top: 16px; }
    .table th { background: #f1f5f9; text-transform: uppercase; font-size: 11px; color: #475569; padding: 8px; text-align: left; }
    .table td { border-top: 1px solid #e2e8f0; padding: 8px; vertical-align: top; font-size: 11px; }
    .table .right { text-align: right; }
    .summary-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; margin-top: 16px; }
    .box { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
    .box-title { font-size: 11px; text-transform: uppercase; font-weight: 600; color: #475569; margin-bottom: 8px; }
    .iva-grid { display: grid; grid-template-columns: 0.6fr 1fr 1fr 1fr; gap: 6px; font-size: 11px; }
    .totals-row { display: flex; justify-content: space-between; margin-top: 6px; }
    .totals-row strong { font-size: 13px; }
    .right { text-align: right; }
    .nota { margin-top: 16px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px; color: #64748b; }
  `;

  printWindow.document.write(`
    <!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <title>${tituloDocumento} ${numero}</title>
        <style>${estilos}</style>
      </head>
      <body>
        ${
          formato === 'POS'
            ? `
              <div class="ticket">
                <div class="center">
                  <p class="subtitle">${infoEmpresa.nombre}</p>
                  <p>${infoEmpresa.nit}</p>
                  <p>${infoEmpresa.regimen}</p>
                  <p>${infoEmpresa.direccion}</p>
                  ${infoEmpresa.telefono ? `<p>Tel: ${infoEmpresa.telefono}</p>` : ''}
                  ${resolucion ? `<p class="label">${resolucion}</p>` : ''}
                </div>
                <div class="line"></div>
                <div class="center">
                  <p class="title">${tituloDocumento}</p>
                  <p class="subtitle">${numero}</p>
                </div>
                <div class="line"></div>
                <div class="row"><span class="label">Medio pago:</span><span class="value">${medioPago || 'N/D'}</span></div>
                <div class="row"><span class="label">Estado:</span><span class="value">${estado || 'N/D'}</span></div>
                <div class="row"><span class="label">Fecha/Hora:</span><span class="value">${fechaFormateada}</span></div>
                <div class="row"><span class="label">Cliente:</span><span class="value">${clienteNombre}</span></div>
                <div class="row"><span class="label">NIT/CC:</span><span class="value">${clienteDocumento}</span></div>
                <div class="line"></div>
                <div class="detalle-title">
                  <span>Descripción</span>
                  <span>Total</span>
                </div>
                ${detallesMostrar
                  .map(
                    (detalle) => `
                      <div class="detalle-item">
                        <p class="detalle-desc">${detalle.descripcion}</p>
                        ${detalle.codigo ? `<p class="label">Código: ${detalle.codigo}</p>` : ''}
                        <div class="detalle-meta">
                          <span>${detalle.cantidad} x ${currencyFormatter.format(detalle.precioUnitario)}</span>
                          <span>${currencyFormatter.format(detalle.total)}</span>
                        </div>
                      </div>
                    `
                  )
                  .join('')}
                <div class="line"></div>
                <div class="totals">
                  <div class="row"><span>Subtotal</span><span>${currencyFormatter.format(subtotal)}</span></div>
                  <div class="row"><span>Impuestos</span><span>${currencyFormatter.format(iva)}</span></div>
                  <div class="row"><span>Descuentos</span><span>-${currencyFormatter.format(descuento)}</span></div>
                  <div class="row total"><span>Total a pagar</span><span>${currencyFormatter.format(total)}</span></div>
                  ${
                    efectivoRecibido !== undefined && cambio !== undefined
                      ? `
                        <div class="row"><span>Recibido</span><span>${currencyFormatter.format(
                          efectivoRecibido
                        )}</span></div>
                        <div class="row"><span>Cambio</span><span>${currencyFormatter.format(cambio)}</span></div>
                      `
                      : ''
                  }
                </div>
                <div class="line"></div>
                <p class="nota">${notas || 'Gracias por su compra. Vuelva pronto.'}</p>
              </div>
            `
            : `
              <div class="sheet">
                <div class="header">
                  <div>
                    <h1>${infoEmpresa.nombre}</h1>
                    <p>${infoEmpresa.nit}</p>
                    <p>${infoEmpresa.regimen}</p>
                    <p>${infoEmpresa.direccion}</p>
                    ${infoEmpresa.telefono ? `<p>Tel: ${infoEmpresa.telefono}</p>` : ''}
                  </div>
                  <div class="doc-title">
                    <p class="label">${tituloDocumento}</p>
                    <p class="doc-number">${numero}</p>
                    <p class="label">${fechaFormateada}</p>
                  </div>
                </div>
                ${resolucion ? `<p class="resolucion">${resolucion}</p>` : ''}
                <div class="grid">
                  <div>
                    <p class="label">Facturado a</p>
                    <p class="section-title">${clienteNombre}</p>
                    <p>NIT/CC: ${clienteDocumento}</p>
                  </div>
                  <div class="doc-title">
                    <p class="label">Medio pago</p>
                    <p class="section-title">${medioPago || 'N/D'}</p>
                    <p>Estado: ${estado || 'N/D'}</p>
                  </div>
                </div>
                <table class="table">
                  <thead>
                    <tr>
                      <th>Descripción</th>
                      <th class="right">Cant.</th>
                      <th class="right">Valor U.</th>
                      <th class="right">Desc.</th>
                      <th class="right">Total</th>
                      <th class="right">IVA</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${detallesMostrar
                      .map(
                        (detalle) => `
                          <tr>
                            <td>
                              <strong>${detalle.descripcion}</strong>
                              ${detalle.codigo ? `<div class="label">Cod. ${detalle.codigo}</div>` : ''}
                            </td>
                            <td class="right">${detalle.cantidad}</td>
                            <td class="right">${currencyFormatter.format(detalle.precioUnitario)}</td>
                            <td class="right">${currencyFormatter.format(detalle.descuento)}</td>
                            <td class="right">${currencyFormatter.format(detalle.total)}</td>
                            <td class="right">${detalle.ivaPorcentaje}%</td>
                          </tr>
                        `
                      )
                      .join('')}
                  </tbody>
                </table>
                <div class="summary-grid">
                  <div class="box">
                    <div class="box-title">Discriminación tarifas IVA</div>
                    <div class="iva-grid">
                      <span class="label">IVA %</span>
                      <span class="label">Base</span>
                      <span class="label">IVA</span>
                      <span class="label">Total</span>
                    </div>
                    ${resumenIvaArray
                      .map(
                        (item) => `
                          <div class="iva-grid">
                            <span>${item.porcentaje}%</span>
                            <span class="right">${currencyFormatter.format(item.base)}</span>
                            <span class="right">${currencyFormatter.format(item.iva)}</span>
                            <span class="right">${currencyFormatter.format(item.total)}</span>
                          </div>
                        `
                      )
                      .join('')}
                  </div>
                  <div class="box">
                    <div class="totals-row"><span>Subtotal</span><span>${currencyFormatter.format(subtotal)}</span></div>
                    <div class="totals-row"><span>Impuestos</span><span>${currencyFormatter.format(iva)}</span></div>
                    <div class="totals-row"><span>Descuento</span><span>-${currencyFormatter.format(descuento)}</span></div>
                    <div class="totals-row"><strong>Total a pagar</strong><strong>${currencyFormatter.format(total)}</strong></div>
                    ${
                      efectivoRecibido !== undefined && cambio !== undefined
                        ? `
                          <div class="totals-row"><span>Recibido</span><span>${currencyFormatter.format(
                            efectivoRecibido
                          )}</span></div>
                          <div class="totals-row"><span>Cambio</span><span>${currencyFormatter.format(cambio)}</span></div>
                        `
                        : ''
                    }
                  </div>
                </div>
                <div class="nota">${notas || 'Gracias por su compra. Vuelva pronto.'}</div>
              </div>
            `
        }
      </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  printWindow.close();
};
