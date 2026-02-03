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

type DocumentoTemplateProps = {
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
  return (
    <div className="mx-auto w-full max-w-[340px] border border-slate-300 bg-white p-4 text-[10px] text-slate-800">
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
