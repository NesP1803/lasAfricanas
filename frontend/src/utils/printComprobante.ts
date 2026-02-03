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

type PrintComprobanteParams = {
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

  const detalleRows = detallesMostrar
    .map(
      (detalle) => `
        <tr>
          <td>
            <strong>${detalle.descripcion}</strong>
            ${detalle.codigo ? `<div class="muted">Código: ${detalle.codigo}</div>` : ''}
            <div class="muted">${detalle.cantidad} x ${currencyFormatter.format(detalle.precioUnitario)}</div>
          </td>
          <td class="right">${currencyFormatter.format(detalle.total)}</td>
        </tr>
      `
    )
    .join('');

  const estilos = `
    :root {
      --ticket-width: 80mm;
      --ticket-padding: 6mm;
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
      padding: var(--ticket-padding);
      color: #0f172a;
      font-size: 10px;
      line-height: 1.2;
      background: #fff;
    }
    h1 { font-size: 11px; text-transform: uppercase; margin: 0; }
    h2 { font-size: 10px; margin: 6px 0; text-transform: uppercase; }
    p { margin: 2px 0; }
    .box { border-top: 1px dashed #94a3b8; margin-top: 6px; padding-top: 6px; }
    .row { display: flex; justify-content: space-between; margin-bottom: 3px; }
    table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 9px; }
    th, td { padding: 3px 0; border-bottom: 1px dashed #cbd5f5; vertical-align: top; }
    th { text-align: left; text-transform: uppercase; font-size: 8px; color: #475569; }
    .right { text-align: right; }
    .muted { color: #64748b; font-size: 8px; }
    .nota { margin-top: 6px; font-size: 8px; color: #64748b; }
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
        <div>
          <div>
            <h1>${infoEmpresa.nombre}</h1>
            <p>${infoEmpresa.nit}</p>
            <p>${infoEmpresa.regimen}</p>
            <p>${infoEmpresa.direccion}</p>
            ${infoEmpresa.telefono ? `<p>Tel: ${infoEmpresa.telefono}</p>` : ''}
            ${resolucion ? `<p class="muted">${resolucion}</p>` : ''}
          </div>
        </div>
        <h2>${tituloDocumento}</h2>
        <p><strong>${numero}</strong></p>
        <p>Fecha: ${fechaFormateada}</p>
        <p>Cliente: ${clienteNombre}</p>
        <p>NIT/CC: ${clienteDocumento}</p>
        <div class="box">
          <div class="row"><span>Medio de pago</span><span>${medioPago || 'N/D'}</span></div>
          <div class="row"><span>Estado</span><span>${estado || 'N/D'}</span></div>
        </div>
        <h2>Detalle</h2>
        <table>
          <thead>
            <tr>
              <th>Descripción</th>
              <th class="right">Total</th>
            </tr>
          </thead>
          <tbody>
            ${detalleRows}
          </tbody>
        </table>
        <div class="box">
          <div class="row"><span>Subtotal</span><span>${currencyFormatter.format(subtotal)}</span></div>
          <div class="row"><span>Impuestos</span><span>${currencyFormatter.format(iva)}</span></div>
          <div class="row"><span>Descuentos</span><span>-${currencyFormatter.format(descuento)}</span></div>
          <div class="row"><strong>Total</strong><strong>${currencyFormatter.format(total)}</strong></div>
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
        <p class="nota">${notas || 'Gracias por su compra. Vuelva pronto.'}</p>
      </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  printWindow.close();
};
