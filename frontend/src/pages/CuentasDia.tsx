import { useEffect, useMemo, useState } from 'react';
import { FileText, Printer, ReceiptText } from 'lucide-react';
import { configuracionAPI } from '../api/configuracion';
import type { ConfiguracionEmpresa } from '../types';
import { ventasApi, type EstadisticasVentas } from '../api/ventas';
import { getLocalDateInputValue } from '../utils/date';

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const toNumber = (value?: string | null) => (value ? Number(value) : 0);

const today = getLocalDateInputValue();
const TICKET_COLS = 42;
const line = () => '='.repeat(TICKET_COLS);
const thinLine = () => '-'.repeat(TICKET_COLS);

const formatTicketDate = (value?: string | null) => {
  if (!value) return '';
  const [year, month, day] = value.split('-').map(Number);
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  return `${day}-${meses[(month || 1) - 1]}-${year}`;
};

function fit(value: string, width: number): string {
  const text = String(value ?? '').toUpperCase();
  if (text.length > width) return text.slice(0, width);
  return text.padEnd(width, ' ');
}

function right(value: string | number, width: number): string {
  const text = String(value ?? '');
  if (text.length > width) return text.slice(0, width);
  return text.padStart(width, ' ');
}

function center(value: string): string {
  const text = String(value ?? '').toUpperCase();
  if (text.length >= TICKET_COLS) return text.slice(0, TICKET_COLS);
  const left = Math.floor((TICKET_COLS - text.length) / 2);
  return ' '.repeat(left) + text;
}

function money(value: string | number | null | undefined): string {
  return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0, minimumFractionDigits: 0 }).format(Number(value ?? 0));
}

function row2(label: string, value: string | number, leftWidth = 22, rightWidth = 18): string {
  return fit(label, leftWidth) + right(value, rightWidth);
}

function section(title: string): string {
  return '\n' + line() + '\n' + center(title) + '\n' + line() + '\n';
}

function ivaHeader() {
  return fit('Tipo', 5) + right('Compra', 10) + right('Base', 10) + right('IVA', 8) + right('Desc', 9);
}

function ivaRow(row: { tipo: string; compra: string; base: string; iva: string; descuento: string }) {
  return fit(row.tipo, 5) + right(money(row.compra), 10) + right(money(row.base), 10) + right(money(row.iva), 8) + right(money(row.descuento), 9);
}

function categoriaHeader() {
  return fit('Categorias', 28) + right('Facturado', 14);
}

function categoriaRow(row: { categoria: string; facturado: string }) {
  return fit(row.categoria, 28) + right(money(row.facturado), 14);
}

function estadoHeader(tipo: 'FACTURAS' | 'REMISIONES') {
  return fit(tipo === 'FACTURAS' ? 'ESTADOS DE FACTURAS' : 'ESTADOS DE REMISIONES', 30) + right('CANTIDAD', 12);
}

function estadoRow(row: { estado: string; cantidad: number }) {
  return fit(row.estado, 30) + right(row.cantidad, 12);
}

function medioPagoHeader(tipo: 'FACTURAS' | 'REMISIONES') {
  return fit(tipo === 'FACTURAS' ? 'No. Facturas' : 'No. Remis.', 10) + fit('Medio Pago', 16) + right('Facturado', 16);
}

function medioPagoRow(row: { cantidad: number; medio_pago: string; facturado: string }) {
  return right(row.cantidad, 10) + fit(row.medio_pago, 16) + right(money(row.facturado), 16);
}

function buildTicketText(tirilla: NonNullable<EstadisticasVentas['resumen_tirilla']>['FACTURA'], tipo: 'FACTURAS' | 'REMISIONES', empresa: ConfiguracionEmpresa | null) {
  const nombreEmpresa = empresa?.razon_social || 'MOTOREPUESTOS LAS AFRICANAS';
  const nitEmpresa = empresa
    ? `${empresa.tipo_identificacion} ${empresa.identificacion}${empresa.dv ? `-${empresa.dv}` : ''}`
    : 'NIT 91.068.915-8';
  const regimen = empresa?.regimen || 'REGIMEN COMUN';
  const telefono = empresa?.telefono || '54350548';
  const direccion = empresa?.direccion || 'CALLE 6 # 12A-45 GAIRA';
  const ciudad = empresa?.ciudad || 'SANTA MARTA MAGDALENA';
  const titulo = tipo === 'FACTURAS' ? 'COMPROBANTE DE FACTURACION' : 'COMPROBANTE DE REMISIONES';
  const rango = `${formatTicketDate(tirilla.fecha_inicio)} A ${formatTicketDate(tirilla.fecha_fin)}`;
  const lines: string[] = [];
  lines.push(center(nombreEmpresa), center(nitEmpresa), center(regimen), center(telefono), center(direccion), center(ciudad), '', center(titulo), center(rango));
  lines.push(section('RESUMEN DE IVA').trimEnd());
  lines.push(ivaHeader());
  for (const row of tirilla.resumen_iva || []) lines.push(ivaRow(row));
  lines.push(thinLine(), center('TOTALES'));
  lines.push(row2('Compra:', money(tirilla.totales_iva?.compra)));
  lines.push(row2('Base:', money(tirilla.totales_iva?.base)));
  lines.push(row2('IVA:', money(tirilla.totales_iva?.iva)));
  lines.push(row2('Descuentos:', money(tirilla.totales_iva?.descuento)));
  lines.push(section('RESUMEN A CATEGORIAS').trimEnd());
  lines.push(categoriaHeader());
  for (const row of tirilla.resumen_categorias || []) lines.push(categoriaRow(row));
  lines.push(thinLine());
  lines.push(row2('TOTAL', money(tirilla.total_facturado), 28, 14));
  lines.push(section('RESUMEN A ESTADOS').trimEnd());
  lines.push(estadoHeader(tipo));
  for (const row of tirilla.resumen_estados || []) lines.push(estadoRow(row));
  lines.push(section('RESUMEN A MEDIO DE PAGO').trimEnd());
  lines.push(medioPagoHeader(tipo));
  for (const row of tirilla.resumen_medios_pago || []) lines.push(medioPagoRow(row));
  lines.push(thinLine());
  lines.push(right('TOTAL', 26) + right(money(tirilla.total_facturado), 16));
  if (tirilla.total_documentos === 0) lines.push('', center('SIN DOCUMENTOS EN EL RANGO'));
  lines.push('');
  return lines.join('\n');
}

const escapeHtml = (value: string) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

export default function CuentasDia() {
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [stats, setStats] = useState<EstadisticasVentas | null>(null);
  const [loading, setLoading] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa | null>(null);

  const cargarEstadisticas = async () => {
    setLoading(true);
    try {
      const response = await ventasApi.getEstadisticas({
        fechaInicio,
        fechaFin,
      });
      setStats(response);
      setMensaje(null);
    } catch (error) {
      setMensaje('No se pudo cargar el cuadre del día. Intenta más tarde.');
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    configuracionAPI
      .obtenerEmpresa()
      .then(setEmpresa)
      .catch(() => setEmpresa(null));
  }, []);

  useEffect(() => {
    if (!fechaInicio || !fechaFin) return;
    if (fechaInicio > fechaFin) {
      setStats(null);
      setMensaje('La fecha inicial no puede ser mayor a la fecha final.');
      return;
    }
    cargarEstadisticas();
  }, [fechaInicio, fechaFin]);

  const facturasValor = useMemo(
    () => toNumber(stats?.total_facturas_valor),
    [stats?.total_facturas_valor]
  );
  const remisionesValor = useMemo(
    () => toNumber(stats?.total_remisiones_valor),
    [stats?.total_remisiones_valor]
  );
  const totalCaja = facturasValor + remisionesValor;

  const imprimirRecibo = async (tipo: 'FACTURAS' | 'REMISIONES') => {
    setPrinting(true);
    try {
      const tirilla = tipo === 'FACTURAS' ? stats?.resumen_tirilla?.FACTURA : stats?.resumen_tirilla?.REMISION;
      if (!tirilla) return;
      const printWindow = window.open('', '_blank', 'width=820,height=700');
      if (!printWindow) {
        setMensaje('No se pudo abrir la ventana de impresión.');
        return;
      }
      const ticketText = buildTicketText(tirilla, tipo, empresa);

      printWindow.document.write(`
        <!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8" />
            <title>${escapeHtml(tirilla.titulo)}</title>
            <style>
              @page { size: 80mm auto; margin: 0; }
              html, body { width: 80mm; margin: 0; padding: 0; }
              html, body { width: 80mm; margin: 0; padding: 0; background: #fff; }
              body { color: #000; }
              .ticket { width: 80mm; box-sizing: border-box; padding: 3mm 3mm 4mm 3mm; }
              .ticket-text {
                margin: 0; padding: 0; white-space: pre;
                font-family: "Courier New", "Lucida Console", monospace;
                font-size: 10px; line-height: 1.15; font-weight: 700; color: #000;
              }
              @media print {
                html, body { width: 80mm; }
                .ticket { width: 80mm; }
                .ticket-text { font-size: 10px; line-height: 1.15; }
              }
            </style>
          </head>
          <body>
            <div class="ticket">
              <pre class="ticket-text">${escapeHtml(ticketText)}</pre>
            </div>
          </body>
        </html>
      `);
      printWindow.document.close();
      printWindow.focus();
      printWindow.print();
      printWindow.close();
    } catch (error) {
      setMensaje('No se pudo generar el recibo. Intenta más tarde.');
    } finally {
      setPrinting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Cuentas del día</h1>
          <p className="text-sm text-slate-500">
            Consulta lo recaudado en facturas y remisiones según el rango de fechas.
          </p>
        </div>
        {loading ? (
          <span className="text-sm font-semibold text-slate-500">Actualizando...</span>
        ) : null}
      </div>

      <section className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[1.2fr,1fr]">
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase text-slate-500">
                Fecha inicio
              </label>
              <input
                type="date"
                value={fechaInicio}
                onChange={(event) => setFechaInicio(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase text-slate-500">
                Fecha final
              </label>
              <input
                type="date"
                value={fechaFin}
                onChange={(event) => setFechaFin(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">
                    Recaudado x facturas
                  </p>
                  <p className="text-2xl font-semibold text-slate-900">
                    {currencyFormatter.format(facturasValor)}
                  </p>
                </div>
                <FileText className="text-blue-600" size={28} />
              </div>
              <p className="mt-2 text-sm text-slate-500">
                {stats?.total_facturas ?? 0} facturas confirmadas.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">
                    Recaudado x remisiones
                  </p>
                  <p className="text-2xl font-semibold text-slate-900">
                    {currencyFormatter.format(remisionesValor)}
                  </p>
                </div>
                <ReceiptText className="text-amber-500" size={28} />
              </div>
              <p className="mt-2 text-sm text-slate-500">
                {stats?.total_remisiones ?? 0} remisiones confirmadas.
              </p>
            </div>
          </div>
        </div>

        <div className="flex h-full flex-col justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              Dinero en caja - entregar cuentas
            </p>
            <p className="mt-3 text-3xl font-bold text-slate-900">
              {currencyFormatter.format(totalCaja)}
            </p>
          </div>
          <div className="grid gap-2">
            <div className="grid gap-2">
              <p className="text-xs font-semibold uppercase text-slate-500">
                Facturas
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => imprimirRecibo('FACTURAS')}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading || printing || !stats}
                >
                  Tirilla
                  <Printer size={18} />
                </button>
              </div>
            </div>
            <div className="grid gap-2">
              <p className="text-xs font-semibold uppercase text-slate-500">
                Remisiones
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => imprimirRecibo('REMISIONES')}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading || printing || !stats}
                >
                  Tirilla
                  <Printer size={18} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {mensaje && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {mensaje}
        </div>
      )}
    </div>
  );
}
