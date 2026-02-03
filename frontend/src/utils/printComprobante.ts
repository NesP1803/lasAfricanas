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

  const estilos = `
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
      </body>
    </html>
  `);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  printWindow.close();
};
