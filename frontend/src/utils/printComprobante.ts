import type { ConfiguracionEmpresa } from '../types';

export type DocumentoDetalle = {
  descripcion: string;
  codigo?: string;
  cantidad: number;
  precioUnitario: number;
  descuento: number;
  subtotal?: number;
  ivaPorcentaje: number;
  ivaValor?: number;
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
  clienteDireccion?: string;
  clienteTelefono?: string;
  clienteEmail?: string;
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
  cufe?: string;
  qrUrl?: string;
  qrImageUrl?: string;
  referenceCode?: string;
  representacionGrafica?: string;
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

const formatFechaDocumento = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return fecha;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'short' }).format(date);
};

const formatHoraDocumento = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('es-CO', { timeStyle: 'short' }).format(date);
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

const getLogoEmpresa = (empresa?: ConfiguracionEmpresa | null) =>
  empresa?.logo || '/logo-default-pos.svg';

const getEstadoVisual = (estado?: string) => {
  const normalized = (estado || '').trim().toUpperCase();
  if (!normalized) return 'N/D';
  if (normalized === 'COBRADA' || normalized === 'COBRADA LOCALMENTE') {
    return 'Facturada';
  }
  return estado || 'N/D';
};

const POLITICAS_CAMBIOS_GARANTIAS =
  'Para trámites de cambios y garantías, indispensable presentar la factura de venta. Tiene hasta 5 días para realizar el trámite. Las partes eléctricas NO tienen devolución. Los productos deben estar en perfecto estado y empaque original.';

export const printComprobante = ({
  formato = 'POS',
  tipo,
  numero,
  fecha,
  clienteNombre,
  clienteDocumento,
  clienteDireccion,
  clienteTelefono,
  clienteEmail,
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
  cufe,
  qrUrl,
  qrImageUrl,
  referenceCode,
  representacionGrafica,
}: PrintComprobanteParams) => {
  const printWindow = window.open('', '_blank', 'width=960,height=860');
  if (!printWindow) return;

  const infoEmpresa = getEmpresaInfo(empresa);
  const fechaFormateada = formatFechaHora(fecha);
  const fechaDocumento = formatFechaDocumento(fecha);
  const horaDocumento = formatHoraDocumento(fecha);
  const tituloDocumento = getTituloDocumento(tipo);
  const estadoVisual = getEstadoVisual(estado);
  const detallesMostrar = detalles.length
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

  const resumenIvaArray = Array.from(
    detallesMostrar.reduce((acc, detalle) => {
      const ivaPorcentaje = Number.isFinite(detalle.ivaPorcentaje) ? detalle.ivaPorcentaje : 0;
      const totalDetalle = Number.isFinite(detalle.total) ? detalle.total : 0;
      const subtotalDetalle = Number.isFinite(detalle.subtotal) ? Number(detalle.subtotal) : NaN;
      const ivaDetalleExplicito = Number.isFinite(detalle.ivaValor) ? Number(detalle.ivaValor) : NaN;
      const divisorIva = 1 + ivaPorcentaje / 100;
      const base = Number.isFinite(subtotalDetalle)
        ? subtotalDetalle
        : (ivaPorcentaje > 0 ? totalDetalle / divisorIva : totalDetalle);
      const ivaDetalle = Number.isFinite(ivaDetalleExplicito) ? ivaDetalleExplicito : (totalDetalle - base);
      const item = acc.get(ivaPorcentaje) || { base: 0, iva: 0, total: 0 };
      acc.set(ivaPorcentaje, {
        base: item.base + base,
        iva: item.iva + ivaDetalle,
        total: item.total + totalDetalle,
      });
      return acc;
    }, new Map<number, { base: number; iva: number; total: number }>())
  ).map(([porcentaje, valores]) => ({ porcentaje, ...valores }));

  const estilos =
    formato === 'POS'
      ? `
      :root { --ticket-width: 80mm; }
      * { box-sizing: border-box; }
      @page { size: 80mm auto; margin: 0; }
      html, body { width: var(--ticket-width); margin: 0; padding: 0; background: #fff; }
      body { font-family: Arial, sans-serif; color: #0f172a; font-size: 10px; line-height: 1.28; }
      .ticket { width: var(--ticket-width); border: 1px solid #cbd5e1; padding: 6px 5px; }
      .content { display: flex; align-items: stretch; gap: 4px; }
      .cufe-side { width: 12px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; padding-left: 1px; }
      .cufe-divider { width: 1px; align-self: stretch; background: #cbd5e1; }
      .cufe-vertical { transform: rotate(180deg); writing-mode: vertical-rl; text-orientation: mixed; font-size: 7px; font-weight: 700; color: #475569; letter-spacing: .08em; line-height: 1.12; max-height: calc(100% - 6px); max-width: 100%; min-width: 0; overflow: hidden; overflow-wrap: anywhere; word-break: break-word; white-space: normal; }
      .main { flex: 1; min-width: 0; }
      .center { text-align: center; }
      .line { border-top: 1px solid #e2e8f0; margin: 6px 0; }
      .muted { color: #64748b; font-size: 8px; }
      .row { display: flex; justify-content: space-between; gap: 6px; margin: 1px 0; }
      .row .value { text-align: right; font-weight: 700; }
      .break { overflow-wrap: anywhere; word-break: break-word; }
      .item { margin: 4px 0; }
      .item strong { display: block; text-transform: uppercase; }
      .total-row { font-size: 11px; font-weight: 700; margin-top: 3px; }
      .qr { margin-top: 1px; text-align: center; }
      .qr img { width: 94px; height: 94px; object-fit: contain; }
      .placeholder { border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px; font-size: 8px; color: #64748b; }
      .logo { display: block; margin: 0 auto 4px; height: 42px; max-width: 52mm; object-fit: contain; border-radius: 5px; }
      .resolution { margin-top: 4px; padding: 2px 0; text-align: left; }
      .resolution-title { font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #475569; }
      .totals-box { border: 1px solid #cbd5e1; margin-top: 6px; padding: 4px; }
      .thank-you { text-align: center; font-size: 9px; font-weight: 600; margin-top: 7px; }
      .doc-datetime { margin-top: 4px; padding: 1px 2px; font-size: 8px; }
      .doc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px 6px; align-items: center; }
      .items-header, .item-row { display: grid; grid-template-columns: 2fr 1fr .75fr; gap: 6px; }
      .items-header { font-size: 8px; font-weight: 700; text-transform: uppercase; color: #334155; }
      .item-row { border-top: 1px solid #e2e8f0; padding-top: 3px; margin-top: 3px; }
      .tiny { font-size: 7px; color: #64748b; }
      .iva-box { border: 1px solid #cbd5e1; margin-top: 6px; padding: 4px; }
      .iva-grid { display: grid; grid-template-columns: .85fr 1fr 1fr 1fr; gap: 4px; align-items: start; }
      .right { text-align: right; }
      .policies { margin-top: 6px; font-size: 8px; line-height: 1.4; color: #334155; padding: 2px 4px; text-align: center; }
    `
      : `
      * { box-sizing: border-box; }
      @page { size: A4; margin: 10mm; }
      body { margin: 0; font-family: Arial, sans-serif; color: #0f172a; font-size: 11px; background: #fff; }
      .sheet { width: 190mm; margin: 0 auto; border: 1px solid #cbd5e1; padding: 8mm; }
      .header { display: grid; grid-template-columns: 1.2fr 1fr; gap: 10mm; border-bottom: 1px solid #e2e8f0; padding-bottom: 4mm; }
      .header h1 { margin: 0; font-size: 15px; text-transform: uppercase; }
      .header p { margin: 1mm 0; }
      .doc { text-align: right; }
      .doc-number { margin: 0; font-size: 20px; font-weight: 700; }
      .logo { display: block; margin-bottom: 2mm; height: 14mm; max-width: 80mm; object-fit: contain; object-position: left; }
      .muted { color: #64748b; font-size: 10px; }
      .break { overflow-wrap: anywhere; word-break: break-word; }
      .qr img { margin-top: 2mm; width: 22mm; height: 22mm; border: 1px solid #e2e8f0; padding: 1mm; }
      .grid { margin-top: 4mm; display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
      .box { border: 1px solid #e2e8f0; padding: 3mm; break-inside: avoid; }
      .table { width: 100%; border-collapse: collapse; margin-top: 4mm; }
      .table th { background: #f1f5f9; text-transform: uppercase; color: #475569; font-size: 10px; text-align: left; }
      .table th, .table td { border: 1px solid #e2e8f0; padding: 2mm; vertical-align: top; }
      .right { text-align: right; }
      .summary { margin-top: 4mm; display: grid; grid-template-columns: 1.3fr 1fr; gap: 4mm; }
      .row { display: flex; justify-content: space-between; margin: 1.4mm 0; }
      .total { border-top: 1px solid #e2e8f0; padding-top: 1.5mm; font-size: 13px; font-weight: 700; }
      .footer { margin-top: 4mm; border: 1px solid #e2e8f0; background: #f8fafc; padding: 3mm; font-size: 10px; }
      .footer p { margin: 1mm 0; }
      .cufe-inline { min-width: 0; max-width: 100%; overflow: hidden; overflow-wrap: anywhere; word-break: break-word; white-space: normal; }
      @media print {
        .sheet { border: 0; width: auto; margin: 0; padding: 0; }
        tr, td, th { break-inside: avoid; }
      }
    `;

  const html = formato === 'POS'
    ? `
      <div class="ticket">
        <div class="content">
          ${cufe ? `<div class="cufe-side"><div class="cufe-vertical">CUFE · ${cufe}</div></div><div class="cufe-divider" aria-hidden="true"></div>` : ''}
          <div class="main">
            <div class="center">
              <img src="${getLogoEmpresa(empresa)}" alt="Logo empresa" class="logo"/>
              <strong>${infoEmpresa.nombre}</strong>
              <div>${infoEmpresa.nit}</div>
              <div>${infoEmpresa.regimen}</div>
              <div class="break">${infoEmpresa.direccion}</div>
              ${infoEmpresa.telefono ? `<div>Tel: ${infoEmpresa.telefono}</div>` : ''}
              <div class="resolution">
                <div class="resolution-title">Resolución / Numeración</div>
                <div class="muted break">${resolucion || 'No informada'}</div>
              </div>
            </div>
            <div class="line"></div>
            <div class="center"><strong>${tituloDocumento}</strong><div><strong>${numero}</strong></div>${referenceCode ? `<div class="muted">Ref: ${referenceCode}</div>` : ''}<div class="doc-datetime"><div class="doc-grid"><span class="muted" style="text-align:left">Fecha:</span><strong style="text-align:right">${fechaDocumento}</strong><span class="muted" style="text-align:left">Hora:</span><strong style="text-align:right">${horaDocumento || fechaFormateada}</strong></div></div></div>
            <div class="line"></div>
            <div class="row"><span>Cliente:</span><span class="value break">${clienteNombre}</span></div>
            <div class="row"><span>NIT/CC:</span><span class="value">${clienteDocumento || 'N/D'}</span></div>
            <div class="row"><span>Pago:</span><span class="value">${medioPago || 'N/D'}</span></div>
            <div class="row"><span>Estado:</span><span class="value">${estadoVisual}</span></div>
            <div class="line"></div>
            <div class="items-header"><span>Descripción</span><span class="right">Valor</span><span class="right">IVA %</span></div>
            ${detallesMostrar
              .map(
                (d) => `<div class="item-row"><div><strong class="break">${d.descripcion}</strong>${d.codigo ? `<div class="tiny">Cod: ${d.codigo}</div>` : ''}<div class="tiny">${d.cantidad} x ${currencyFormatter.format(d.precioUnitario)}</div></div><strong class="right">${currencyFormatter.format(d.total)}</strong><span class="right">${Number.isFinite(d.ivaPorcentaje) ? d.ivaPorcentaje : 0}%</span></div>`
              )
              .join('')}
            <div class="totals-box">
              <div class="row"><span>Subtotal</span><span>${currencyFormatter.format(subtotal)}</span></div>
              <div class="row"><span>Impuestos</span><span>${currencyFormatter.format(iva)}</span></div>
              <div class="row"><span>Descuentos</span><span>-${currencyFormatter.format(descuento)}</span></div>
              <div class="row total-row"><span>Total a pagar</span><span>${currencyFormatter.format(total)}</span></div>
              ${efectivoRecibido !== undefined && cambio !== undefined ? `<div class="row"><span>Recibido</span><span>${currencyFormatter.format(efectivoRecibido)}</span></div><div class="row"><span>Cambio</span><span>${currencyFormatter.format(cambio)}</span></div>` : ''}
            </div>
            <div class="iva-box">
              <div style="font-size:8px;font-weight:700;text-transform:uppercase;color:#334155;">Discriminación IVA</div>
              <div class="iva-grid muted" style="font-size:7px;font-weight:700;text-transform:uppercase;margin-top:2px;">
                <span>Tarifa</span><span class="right">Valor compra</span><span class="right">Base/Imp</span><span class="right">Valor IVA</span>
              </div>
              ${resumenIvaArray.map((item) => `<div class="iva-grid" style="margin-top:2px;"><span>${item.porcentaje}%</span><span class="right">${currencyFormatter.format(item.total)}</span><span class="right">${currencyFormatter.format(item.base)}</span><span class="right">${currencyFormatter.format(item.iva)}</span></div>`).join('')}
            </div>
            ${notas ? `<div class="muted break">${notas}</div>` : ''}
            <div class="qr">
              ${qrImageUrl ? `<img src="${qrImageUrl}" alt="QR factura electrónica"/>` : qrUrl ? `<div class="muted break">Verificación: ${qrUrl}</div>` : '<div class="placeholder">Espacio reservado para QR DIAN</div>'}
            </div>
            <div class="policies">${POLITICAS_CAMBIOS_GARANTIAS}</div>
            <div class="thank-you">Gracias por su compra, es un placer atenderlo.</div>
          </div>
        </div>
      </div>
    `
    : `
      <div class="sheet">
        <div class="header">
          <div>
            <img src="${getLogoEmpresa(empresa)}" alt="Logo empresa" class="logo"/>
            <h1>${infoEmpresa.nombre}</h1>
            <p>${infoEmpresa.nit}</p>
            <p>${infoEmpresa.regimen}</p>
            <p class="break">${infoEmpresa.direccion}</p>
            ${infoEmpresa.telefono ? `<p>Tel: ${infoEmpresa.telefono}</p>` : ''}
          </div>
          <div class="doc">
            <p class="muted">${tituloDocumento}</p>
            <p class="doc-number">${numero}</p>
            ${referenceCode ? `<p class="muted">Doc. Ref: ${referenceCode}</p>` : ''}
            ${qrImageUrl ? `<div class="qr"><img src="${qrImageUrl}" alt="QR factura electrónica"/></div>` : qrUrl ? `<p class="muted break">${qrUrl}</p>` : ''}
          </div>
        </div>
        ${resolucion ? `<p class="muted" style="margin-top:3mm;">${resolucion}</p>` : ''}
        <div class="grid">
          <div class="box">
            <p class="muted" style="text-transform:uppercase;margin:0;">Datos cliente</p>
            <p><strong>${clienteNombre}</strong></p>
            <p>NIT/CC: ${clienteDocumento || 'N/D'}</p>
            ${clienteDireccion ? `<p class="break">Dir: ${clienteDireccion}</p>` : ''}
            ${clienteTelefono ? `<p>Tel: ${clienteTelefono}</p>` : ''}
            ${clienteEmail ? `<p class="break">Email: ${clienteEmail}</p>` : ''}
          </div>
          <div class="box" style="text-align:right;">
            <p><span class="muted">Fecha/Hora:</span> <strong>${fechaFormateada}</strong></p>
            <p><span class="muted">Medio pago:</span> <strong>${medioPago || 'N/D'}</strong></p>
            <p><span class="muted">Estado:</span> <strong>${estado || 'N/D'}</strong></p>
          </div>
        </div>
        <table class="table">
          <thead><tr><th>Descripción</th><th class="right">Cant.</th><th class="right">Vlr U.</th><th class="right">Desc.</th><th class="right">Total</th><th class="right">IVA</th></tr></thead>
          <tbody>
            ${detallesMostrar.map((d) => `<tr><td><strong class="break">${d.descripcion}</strong>${d.codigo ? `<div class="muted">Cod. ${d.codigo}</div>` : ''}</td><td class="right">${d.cantidad}</td><td class="right">${currencyFormatter.format(d.precioUnitario)}</td><td class="right">${currencyFormatter.format(d.descuento)}</td><td class="right">${currencyFormatter.format(d.total)}</td><td class="right">${d.ivaPorcentaje}%</td></tr>`).join('')}
          </tbody>
        </table>
        <div class="summary">
          <div class="box">
            <p class="muted" style="text-transform:uppercase;margin:0;">Discriminación IVA</p>
            <div class="row muted"><span>IVA%</span><span>Base</span><span>IVA</span><span>Total</span></div>
            ${resumenIvaArray.map((item) => `<div class="row"><span>${item.porcentaje}%</span><span>${currencyFormatter.format(item.base)}</span><span>${currencyFormatter.format(item.iva)}</span><span>${currencyFormatter.format(item.total)}</span></div>`).join('')}
          </div>
          <div class="box">
            <div class="row"><span>Subtotal</span><strong>${currencyFormatter.format(subtotal)}</strong></div>
            <div class="row"><span>Impuestos</span><strong>${currencyFormatter.format(iva)}</strong></div>
            <div class="row"><span>Descuento</span><strong>-${currencyFormatter.format(descuento)}</strong></div>
            <div class="row total"><span>Total a pagar</span><span>${currencyFormatter.format(total)}</span></div>
            ${efectivoRecibido !== undefined && cambio !== undefined ? `<div class="row"><span>Recibido</span><span>${currencyFormatter.format(efectivoRecibido)}</span></div><div class="row"><span>Cambio</span><span>${currencyFormatter.format(cambio)}</span></div>` : ''}
          </div>
        </div>
        <div class="footer">
          ${cufe ? `<p class="cufe-inline"><strong>CUFE:</strong> ${cufe}</p>` : ''}
          ${representacionGrafica ? `<p>${representacionGrafica}</p>` : ''}
          ${qrUrl ? `<p class="break">Verificación DIAN: ${qrUrl}</p>` : ''}
          <p>${notas || 'Gracias por su compra. Presentar factura para garantías y devoluciones.'}</p>
        </div>
      </div>
    `;

  printWindow.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"/><title>${tituloDocumento} ${numero}</title><style>${estilos}</style></head><body>${html}</body></html>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
  printWindow.close();
};
