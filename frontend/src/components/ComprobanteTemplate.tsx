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

type DocumentoFormato = 'POS' | 'CARTA';
type DocumentoTipo = 'FACTURA' | 'REMISION' | 'COTIZACION';

type DocumentoTemplateProps = {
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

export default function ComprobanteTemplate({
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
}: DocumentoTemplateProps) {
  const infoEmpresa = getEmpresaInfo(empresa);
  const fechaFormateada = formatFechaHora(fecha);
  const tituloDocumento =
    tipo === 'COTIZACION' ? 'Cotización' : tipo === 'REMISION' ? 'Remisión' : 'Factura de venta';
  const detallesDisponibles = detalles.length > 0;
  const detallesMostrar = detallesDisponibles
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
  if (formato === 'CARTA') {
    const resumenIva = detallesMostrar.reduce((acc, detalle) => {
      const base = detalle.cantidad * detalle.precioUnitario - detalle.descuento;
      const ivaDetalle = base * (detalle.ivaPorcentaje / 100);
      const totalDetalle = base + ivaDetalle;
      const item = acc.get(detalle.ivaPorcentaje) || { base: 0, iva: 0, total: 0 };
      acc.set(detalle.ivaPorcentaje, {
        base: item.base + base,
        iva: item.iva + ivaDetalle,
        total: item.total + totalDetalle,
      });
      return acc;
    }, new Map<number, { base: number; iva: number; total: number }>());
    const resumenIvaArray = Array.from(resumenIva.entries()).map(([porcentaje, valores]) => ({
      porcentaje,
      ...valores,
    }));

    return (
      <div className="mx-auto w-full max-w-3xl border border-slate-300 bg-white p-6 text-xs text-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="text-sm font-semibold uppercase">{infoEmpresa.nombre}</p>
            <p>{infoEmpresa.nit}</p>
            <p>{infoEmpresa.regimen}</p>
            <p>{infoEmpresa.direccion}</p>
            {infoEmpresa.telefono ? <p>Tel: {infoEmpresa.telefono}</p> : null}
          </div>
          <div className="text-right">
            <p className="text-xs uppercase text-slate-500">{tituloDocumento}</p>
            <p className="text-lg font-semibold">{numero}</p>
            <p className="text-xs text-slate-500">{fechaFormateada}</p>
          </div>
        </div>

        {resolucion ? (
          <p className="mt-2 text-[10px] text-slate-500">{resolucion}</p>
        ) : null}

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <p className="text-[11px] uppercase text-slate-500">Facturado a</p>
            <p className="text-sm font-semibold">{clienteNombre}</p>
            <p className="text-xs">NIT/CC: {clienteDocumento}</p>
          </div>
          <div className="space-y-1 text-right">
            <p className="text-[11px] uppercase text-slate-500">Medio pago</p>
            <p className="text-sm font-semibold">{medioPago || 'N/D'}</p>
            <p className="text-xs">Estado: {estado || 'N/D'}</p>
          </div>
        </div>

        <div className="mt-4 border border-slate-200">
          <div className="grid grid-cols-[2.5fr,0.7fr,1fr,1fr,1fr,0.7fr] gap-2 bg-slate-100 px-3 py-2 text-[11px] font-semibold uppercase text-slate-600">
            <span>Descripción</span>
            <span className="text-center">Cant.</span>
            <span className="text-right">Valor U.</span>
            <span className="text-right">Desc.</span>
            <span className="text-right">Total</span>
            <span className="text-right">IVA</span>
          </div>
          {detallesMostrar.map((detalle, index) => (
            <div
              key={`${detalle.descripcion}-${index}`}
              className="grid grid-cols-[2.5fr,0.7fr,1fr,1fr,1fr,0.7fr] gap-2 border-t border-slate-200 px-3 py-2 text-[11px]"
            >
              <div>
                <p className="font-semibold text-slate-700">{detalle.descripcion}</p>
                {detalle.codigo ? (
                  <p className="text-[10px] text-slate-500">Cod. {detalle.codigo}</p>
                ) : null}
              </div>
              <span className="text-center">{detalle.cantidad}</span>
              <span className="text-right">{currencyFormatter.format(detalle.precioUnitario)}</span>
              <span className="text-right">{currencyFormatter.format(detalle.descuento)}</span>
              <span className="text-right">{currencyFormatter.format(detalle.total)}</span>
              <span className="text-right">{detalle.ivaPorcentaje}%</span>
            </div>
          ))}
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-[1.2fr,1fr]">
          <div className="rounded border border-slate-200 p-3">
            <p className="text-[11px] font-semibold uppercase text-slate-600">
              Discriminación tarifas IVA
            </p>
            <div className="mt-2 grid grid-cols-[0.6fr,1fr,1fr,1fr] text-[11px] text-slate-600">
              <span>IVA %</span>
              <span className="text-right">Base</span>
              <span className="text-right">IVA</span>
              <span className="text-right">Total</span>
            </div>
            {resumenIvaArray.map((item) => (
              <div
                key={`iva-${item.porcentaje}`}
                className="mt-1 grid grid-cols-[0.6fr,1fr,1fr,1fr] text-[11px]"
              >
                <span>{item.porcentaje}%</span>
                <span className="text-right">{currencyFormatter.format(item.base)}</span>
                <span className="text-right">{currencyFormatter.format(item.iva)}</span>
                <span className="text-right">{currencyFormatter.format(item.total)}</span>
              </div>
            ))}
          </div>
          <div className="space-y-2 rounded border border-slate-200 p-3 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-500">Subtotal</span>
              <span className="font-semibold">{currencyFormatter.format(subtotal)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Impuestos</span>
              <span className="font-semibold">{currencyFormatter.format(iva)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Descuento</span>
              <span className="font-semibold">-{currencyFormatter.format(descuento)}</span>
            </div>
            <div className="flex justify-between text-sm font-semibold">
              <span>Total a pagar</span>
              <span>{currencyFormatter.format(total)}</span>
            </div>
            {efectivoRecibido !== undefined && cambio !== undefined ? (
              <>
                <div className="flex justify-between">
                  <span className="text-slate-500">Recibido</span>
                  <span className="font-semibold">
                    {currencyFormatter.format(efectivoRecibido)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Cambio</span>
                  <span className="font-semibold">{currencyFormatter.format(cambio)}</span>
                </div>
              </>
            ) : null}
          </div>
        </div>

        <div className="mt-4 rounded border border-slate-200 bg-slate-50 p-3 text-[10px] text-slate-500">
          {notas || 'Gracias por su compra. Presentar factura para garantías y devoluciones.'}
        </div>
      </div>
    );
  }
  return (
    <div className="mx-auto w-full max-w-[80mm] border border-slate-300 bg-white p-4 text-[10px] text-slate-800">
      <div className="text-center">
        <p className="text-xs font-semibold uppercase">{infoEmpresa.nombre}</p>
        <p>{infoEmpresa.nit}</p>
        <p>{infoEmpresa.regimen}</p>
        <p>{infoEmpresa.direccion}</p>
        {infoEmpresa.telefono ? <p>Tel: {infoEmpresa.telefono}</p> : null}
        {resolucion ? <p className="mt-1 text-[9px] text-slate-500">{resolucion}</p> : null}
      </div>

      <div className="mt-3 border-t border-dashed border-slate-400 pt-2 text-center">
        <p className="text-[11px] font-semibold uppercase">{tituloDocumento}</p>
        <p className="text-xs font-semibold">{numero}</p>
      </div>

      <div className="mt-2 space-y-1 text-[10px]">
        <div className="flex justify-between">
          <span>Medio pago:</span>
          <span className="font-semibold">{medioPago || 'N/D'}</span>
        </div>
        <div className="flex justify-between">
          <span>Estado:</span>
          <span className="font-semibold">{estado || 'N/D'}</span>
        </div>
        <div className="flex justify-between">
          <span>Fecha/Hora:</span>
          <span className="font-semibold">{fechaFormateada}</span>
        </div>
        <div className="flex justify-between">
          <span>Cliente:</span>
          <span className="font-semibold">{clienteNombre}</span>
        </div>
        <div className="flex justify-between">
          <span>NIT/CC:</span>
          <span className="font-semibold">{clienteDocumento}</span>
        </div>
      </div>

      <div className="mt-2 border-t border-dashed border-slate-400 pt-2">
        <div className="flex justify-between font-semibold">
          <span>Descripción</span>
          <span>Total</span>
        </div>
        {detallesMostrar.map((detalle, index) => (
          <div key={`${detalle.descripcion}-${index}`} className="mt-1">
            <p className="uppercase">{detalle.descripcion}</p>
            <div className="flex justify-between text-[9px] text-slate-600">
              <span>
                {detalle.cantidad} x {currencyFormatter.format(detalle.precioUnitario)}
              </span>
              <span>{currencyFormatter.format(detalle.total)}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-2 border-t border-dashed border-slate-400 pt-2">
        <div className="flex justify-between">
          <span>Subtotal</span>
          <span>{currencyFormatter.format(subtotal)}</span>
        </div>
        <div className="flex justify-between">
          <span>Impuestos</span>
          <span>{currencyFormatter.format(iva)}</span>
        </div>
        <div className="flex justify-between">
          <span>Descuentos</span>
          <span>-{currencyFormatter.format(descuento)}</span>
        </div>
        <div className="mt-1 flex justify-between text-[11px] font-semibold">
          <span>Total a pagar</span>
          <span>{currencyFormatter.format(total)}</span>
        </div>
        {efectivoRecibido !== undefined && cambio !== undefined ? (
          <>
            <div className="flex justify-between">
              <span>Recibido</span>
              <span>{currencyFormatter.format(efectivoRecibido)}</span>
            </div>
            <div className="flex justify-between">
              <span>Cambio</span>
              <span>{currencyFormatter.format(cambio)}</span>
            </div>
          </>
        ) : null}
      </div>

      <div className="mt-2 border-t border-dashed border-slate-400 pt-2 text-[9px] text-slate-500">
        {notas || 'Gracias por su compra. Vuelva pronto.'}
      </div>
    </div>
  );
}
