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

type DocumentoTemplateProps = {
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

export default function ComprobanteTemplate({
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
}: DocumentoTemplateProps) {
  const infoEmpresa = getEmpresaInfo(empresa);
  const fechaFormateada = formatFechaHora(fecha);
  const fechaDocumento = formatFechaDocumento(fecha);
  const horaDocumento = formatHoraDocumento(fecha);
  const tituloDocumento = getTituloDocumento(tipo);
  const estadoVisual = getEstadoVisual(estado);
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

  if (formato === 'CARTA') {
    return (
      <div className="mx-auto w-full max-w-[210mm] border border-slate-300 bg-white p-7 font-sans text-[11px] text-slate-800">
        <header className="grid grid-cols-[1.2fr,1fr] gap-6 border-b border-slate-200 pb-4">
          <div className="space-y-1">
            <img
              src={getLogoEmpresa(empresa)}
              alt="Logo empresa"
              className="mb-2 h-14 max-w-[80mm] rounded-md object-contain object-left"
            />
            <p className="text-base font-bold uppercase tracking-wide">{infoEmpresa.nombre}</p>
            <p>{infoEmpresa.nit}</p>
            <p>{infoEmpresa.regimen}</p>
            <p className="break-words">{infoEmpresa.direccion}</p>
            {infoEmpresa.telefono ? <p>Tel: {infoEmpresa.telefono}</p> : null}
          </div>
          <div className="space-y-1 text-right">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">{tituloDocumento}</p>
            <p className="text-xl font-bold leading-tight">{numero}</p>
            {referenceCode ? <p className="text-[10px] text-slate-500">Doc. Ref: {referenceCode}</p> : null}
            {qrImageUrl ? (
              <img src={qrImageUrl} alt="QR factura electrónica" className="ml-auto mt-2 h-20 w-20 border border-slate-200 p-1" />
            ) : qrUrl ? (
              <p className="break-all text-[10px] text-slate-600">{qrUrl}</p>
            ) : null}
          </div>
        </header>

        {resolucion ? <p className="mt-3 text-[10px] text-slate-600">{resolucion}</p> : null}

        <section className="mt-4 grid grid-cols-2 gap-4">
          <div className="rounded border border-slate-200 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Datos cliente</p>
            <p className="mt-1 font-semibold">{clienteNombre}</p>
            <p>NIT/CC: {clienteDocumento || 'N/D'}</p>
            {clienteDireccion ? <p className="break-words">Dir: {clienteDireccion}</p> : null}
            {clienteTelefono ? <p>Tel: {clienteTelefono}</p> : null}
            {clienteEmail ? <p className="break-all">Email: {clienteEmail}</p> : null}
          </div>
          <div className="rounded border border-slate-200 p-3 text-right">
            <p><span className="text-slate-500">Fecha/Hora:</span> <span className="font-semibold">{fechaFormateada}</span></p>
            <p><span className="text-slate-500">Medio pago:</span> <span className="font-semibold">{medioPago || 'N/D'}</span></p>
            <p><span className="text-slate-500">Estado:</span> <span className="font-semibold">{estado || 'N/D'}</span></p>
          </div>
        </section>

        <section className="mt-4 overflow-hidden border border-slate-200">
          <div className="grid grid-cols-[2.6fr,0.6fr,1fr,0.9fr,1fr,0.6fr] gap-2 bg-slate-100 px-3 py-2 text-[10px] font-semibold uppercase text-slate-600">
            <span>Descripción</span><span className="text-center">Cant.</span><span className="text-right">Vlr U.</span><span className="text-right">Desc.</span><span className="text-right">Total</span><span className="text-right">IVA</span>
          </div>
          {detallesMostrar.map((detalle, index) => (
            <div key={`${detalle.descripcion}-${index}`} className="grid break-inside-avoid grid-cols-[2.6fr,0.6fr,1fr,0.9fr,1fr,0.6fr] gap-2 border-t border-slate-200 px-3 py-2 text-[10px]">
              <div className="min-w-0"><p className="font-semibold break-words">{detalle.descripcion}</p>{detalle.codigo ? <p className="text-[9px] text-slate-500">Cod. {detalle.codigo}</p> : null}</div>
              <span className="text-center">{detalle.cantidad}</span>
              <span className="text-right">{currencyFormatter.format(detalle.precioUnitario)}</span>
              <span className="text-right">{currencyFormatter.format(detalle.descuento)}</span>
              <span className="text-right">{currencyFormatter.format(detalle.total)}</span>
              <span className="text-right">{detalle.ivaPorcentaje}%</span>
            </div>
          ))}
        </section>

        <section className="mt-4 grid grid-cols-[1.3fr,1fr] gap-4">
          <div className="rounded border border-slate-200 p-3">
            <p className="text-[10px] font-semibold uppercase text-slate-600">Discriminación IVA</p>
            <div className="mt-2 grid grid-cols-[0.6fr,1fr,1fr,1fr] text-[10px] text-slate-500"><span>IVA%</span><span className="text-right">Base</span><span className="text-right">IVA</span><span className="text-right">Total</span></div>
            {resumenIvaArray.map((item) => (
              <div key={`iva-${item.porcentaje}`} className="mt-1 grid grid-cols-[0.6fr,1fr,1fr,1fr] text-[10px]"><span>{item.porcentaje}%</span><span className="text-right">{currencyFormatter.format(item.base)}</span><span className="text-right">{currencyFormatter.format(item.iva)}</span><span className="text-right">{currencyFormatter.format(item.total)}</span></div>
            ))}
          </div>
          <div className="rounded border border-slate-200 p-3 text-[10px]">
            <div className="flex justify-between"><span>Subtotal</span><span className="font-semibold">{currencyFormatter.format(subtotal)}</span></div>
            <div className="mt-1 flex justify-between"><span>Impuestos</span><span className="font-semibold">{currencyFormatter.format(iva)}</span></div>
            <div className="mt-1 flex justify-between"><span>Descuento</span><span className="font-semibold">-{currencyFormatter.format(descuento)}</span></div>
            <div className="mt-2 flex justify-between border-t border-slate-200 pt-2 text-sm font-bold"><span>Total a pagar</span><span>{currencyFormatter.format(total)}</span></div>
            {efectivoRecibido !== undefined && cambio !== undefined ? (
              <>
                <div className="mt-1 flex justify-between"><span>Recibido</span><span>{currencyFormatter.format(efectivoRecibido)}</span></div>
                <div className="mt-1 flex justify-between"><span>Cambio</span><span>{currencyFormatter.format(cambio)}</span></div>
              </>
            ) : null}
          </div>
        </section>

        <footer className="mt-4 rounded border border-slate-200 bg-slate-50 p-3 text-[10px] text-slate-600">
          {cufe ? (
            <p className="min-w-0 max-w-full overflow-hidden whitespace-normal break-all">
              <span className="font-semibold text-slate-700">CUFE:</span> {cufe}
            </p>
          ) : null}
          {representacionGrafica ? <p className="mt-1">{representacionGrafica}</p> : null}
          {qrUrl ? <p className="mt-1 break-all">Verificación DIAN: {qrUrl}</p> : null}
          <p className="mt-1">{notas || 'Gracias por su compra. Presentar factura para garantías y devoluciones.'}</p>
        </footer>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[82mm] border border-slate-300 bg-white px-1.5 py-2 font-sans text-[10px] text-slate-900">
      <div className={`flex items-stretch ${cufe ? 'gap-1' : ''}`}>
        {cufe ? (
          <aside className="flex w-[12px] shrink-0 items-center justify-center">
            <p className="max-h-[calc(100%-6px)] overflow-hidden whitespace-normal break-all text-[7px] font-semibold leading-tight tracking-[0.08em] text-slate-600 [writing-mode:vertical-rl] [text-orientation:mixed] [transform:rotate(180deg)]">
              CUFE · {cufe}
            </p>
          </aside>
        ) : null}
        {cufe ? <span className="w-px self-stretch bg-slate-300" aria-hidden="true" /> : null}
        <div className="min-w-0 flex-1">
          <div className="text-center">
            <img src={getLogoEmpresa(empresa)} alt="Logo empresa" className="mx-auto mb-1.5 h-11 max-w-[52mm] rounded-lg object-contain" />
            <p className="text-[11px] font-bold uppercase tracking-wide">{infoEmpresa.nombre}</p>
            <p className="text-[9px]">{infoEmpresa.nit}</p>
            <p className="text-[9px]">{infoEmpresa.regimen}</p>
            <p className="break-words">{infoEmpresa.direccion}</p>
            {infoEmpresa.telefono ? <p className="text-[9px]">Tel: {infoEmpresa.telefono}</p> : null}
            <div className="mt-1 px-0.5 py-1 text-left">
              <p className="text-[8px] font-semibold uppercase tracking-wide text-slate-600">Resolución / Numeración</p>
              <p className="break-words text-[8px] text-slate-700">{resolucion || 'No informada'}</p>
            </div>
          </div>

          <div className="mt-2 border-y border-slate-300 py-2 text-center">
            <p className="text-[11px] font-bold uppercase">{tituloDocumento}</p>
            <p className="font-semibold">{numero}</p>
            {referenceCode ? <p className="text-[8px] text-slate-600">Ref: {referenceCode}</p> : null}
            <div className="mt-1 grid grid-cols-[auto,1fr] gap-x-1 gap-y-0.5 px-0 py-0 text-[8px]">
            <span className="text-left text-slate-600">Fecha:</span>
            <span className="text-left font-semibold text-slate-800">{fechaDocumento}</span>
            <span className="text-left text-slate-600">Hora:</span>
            <span className="text-left font-semibold text-slate-800">{horaDocumento || fechaFormateada}</span>
          </div>
          </div>

          <div className="mt-2 space-y-1 text-[9px]">
            <div className="flex justify-between gap-2"><span>Cliente:</span><span className="truncate font-semibold">{clienteNombre}</span></div>
            <div className="flex justify-between gap-2"><span>NIT/CC:</span><span className="font-semibold">{clienteDocumento || 'N/D'}</span></div>
            <div className="flex justify-between gap-2"><span>Pago:</span><span className="font-semibold">{medioPago || 'N/D'}</span></div>
            <div className="flex justify-between gap-2"><span>Estado:</span><span className="font-semibold">{estadoVisual}</span></div>
          </div>

          <div className="mt-2 border-t border-slate-300 pt-2">
            <div className="grid grid-cols-[2fr,1fr,0.75fr] gap-2 text-[8px] font-semibold uppercase tracking-wide text-slate-700">
              <span>Descripción</span>
              <span className="text-right">Valor</span>
              <span className="text-right">IVA %</span>
            </div>
            {detallesMostrar.map((detalle, index) => (
              <div key={`${detalle.descripcion}-${index}`} className="mt-1 border-t border-slate-200 pt-1 text-[8px]">
                <div className="grid grid-cols-[2fr,1fr,0.75fr] gap-2">
                  <div className="min-w-0">
                    <p className="break-words uppercase leading-tight">{detalle.descripcion}</p>
                    <p className="text-[7px] text-slate-600">
                      {detalle.cantidad} x {currencyFormatter.format(detalle.precioUnitario)}
                    </p>
                  </div>
                  <span className="text-right font-semibold">{currencyFormatter.format(detalle.total)}</span>
                  <span className="text-right">{Number.isFinite(detalle.ivaPorcentaje) ? detalle.ivaPorcentaje : 0}%</span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-2 rounded border border-slate-300 p-1.5 text-[9px]">
            <div className="flex justify-between"><span>Subtotal</span><span>{currencyFormatter.format(subtotal)}</span></div>
            <div className="flex justify-between"><span>Impuestos</span><span>{currencyFormatter.format(iva)}</span></div>
            <div className="flex justify-between"><span>Descuentos</span><span>-{currencyFormatter.format(descuento)}</span></div>
            <div className="mt-1 flex justify-between border-t border-slate-300 pt-1 text-[11px] font-bold"><span>Total a pagar</span><span>{currencyFormatter.format(total)}</span></div>
            {efectivoRecibido !== undefined && cambio !== undefined ? (
              <>
                <div className="flex justify-between"><span>Recibido</span><span>{currencyFormatter.format(efectivoRecibido)}</span></div>
                <div className="flex justify-between"><span>Cambio</span><span>{currencyFormatter.format(cambio)}</span></div>
              </>
            ) : null}
          </div>

          <div className="mt-2 rounded border border-slate-300 p-1.5 text-[8px]">
            <p className="font-semibold uppercase tracking-wide text-slate-700">Discriminación IVA</p>
            <div className="mt-1 grid grid-cols-[0.85fr,1fr,1fr,1fr] gap-1 text-[7px] font-semibold uppercase text-slate-600">
              <span>Tarifa</span>
              <span className="text-right">Valor compra</span>
              <span className="text-right">Base/Imp</span>
              <span className="text-right">Valor IVA</span>
            </div>
            {resumenIvaArray.map((item) => (
              <div key={`iva-pos-${item.porcentaje}`} className="mt-0.5 grid grid-cols-[0.85fr,1fr,1fr,1fr] gap-1 text-[8px]">
                <span>{item.porcentaje}%</span>
                <span className="text-right">{currencyFormatter.format(item.total)}</span>
                <span className="text-right">{currencyFormatter.format(item.base)}</span>
                <span className="text-right">{currencyFormatter.format(item.iva)}</span>
              </div>
            ))}
          </div>

          <div className="mt-2 pt-2 text-[8px] text-slate-600">
            {notas ? <p className="break-words">{notas}</p> : null}
          </div>

          <div className="mt-1 text-center">
            {qrImageUrl ? (
              <img src={qrImageUrl} alt="QR factura electrónica" className="mx-auto h-24 w-24 object-contain" />
            ) : qrUrl ? (
              <p className="break-all text-[8px]">Verificación: {qrUrl}</p>
            ) : (
              <div className="rounded border border-slate-300 p-2 text-[8px] text-slate-500">Espacio reservado para QR DIAN</div>
            )}
          </div>
          <p className="mt-2 px-1 text-center text-[8px] leading-relaxed text-slate-700">
            {POLITICAS_CAMBIOS_GARANTIAS}
          </p>
          <p className="mt-2 text-center text-[9px] font-medium">
            Gracias por su compra, es un placer atenderlo.
          </p>
        </div>
      </div>
    </div>
  );
}
