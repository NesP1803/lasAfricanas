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
const TICKET_SEPARATOR = '--------------------------------';
const formatTicketMoney = (value?: string | number | null) =>
  new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const formatTicketDate = (value?: string | null) => {
  if (!value) return '';
  const [year, month, day] = value.split('-').map(Number);
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  return `${day}-${meses[(month || 1) - 1]}-${year}`;
};
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
      const renderRows = (rows: string[]) => rows.join('');
      const nombreEmpresa = (empresa?.razon_social || 'MOTOREPUESTOS LAS AFRICANAS').toUpperCase();
      const nitEmpresa = empresa
        ? `${empresa.tipo_identificacion} ${empresa.identificacion}${empresa.dv ? `-${empresa.dv}` : ''}`
        : 'NIT 91.068.915-8';
      const regimen = (empresa?.regimen || 'Régimen común').toUpperCase();
      const telefono = empresa?.telefono || '54350548';
      const direccion = (empresa?.direccion || 'Calle 6 # 12A-45 Gaira').toUpperCase();
      const ciudad = `${empresa?.ciudad || 'Santa Marta'} ${empresa?.municipio || 'Magdalena'}`.toUpperCase();
      const rango = `${formatTicketDate(tirilla.fecha_inicio)} A ${formatTicketDate(tirilla.fecha_fin)}`;
      const estadoTitulo = tipo === 'FACTURAS' ? 'ESTADOS DE FACTURAS' : 'ESTADOS DE REMISIONES';
      const medioTitulo = tipo === 'FACTURAS' ? 'No. de Facturas' : 'No. de Remisiones';
      const ivaRows = renderRows((tirilla.resumen_iva || []).map((row) => `<tr><td>${escapeHtml(row.tipo)}</td><td class="right">${formatTicketMoney(row.compra)}</td><td class="right">${formatTicketMoney(row.base)}</td><td class="right">${formatTicketMoney(row.iva)}</td><td class="right">${formatTicketMoney(row.descuento)}</td></tr>`));
      const categoriaRows = renderRows((tirilla.resumen_categorias || []).map((row) => `<tr><td>${escapeHtml(row.categoria)}</td><td class="right">${formatTicketMoney(row.facturado)}</td></tr>`));
      const estadoRows = renderRows((tirilla.resumen_estados || []).map((row) => `<tr><td>${escapeHtml(row.estado)}</td><td class="right">${row.cantidad}</td></tr>`));
      const medioRows = renderRows((tirilla.resumen_medios_pago || []).map((row) => `<tr><td class="right">${row.cantidad}</td><td>${escapeHtml(row.medio_pago)}</td><td class="right">${formatTicketMoney(row.facturado)}</td></tr>`));
      const sinDocumentos = tirilla.total_documentos === 0 ? '<p class="center">SIN DOCUMENTOS EN EL RANGO</p>' : '';

      printWindow.document.write(`
        <!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8" />
            <title>${escapeHtml(tirilla.titulo)}</title>
            <style>
              @page { size: 80mm auto; margin: 0; }
              html, body { width: 80mm; margin: 0; padding: 0; }
              body { font-family: 'Arial Narrow', monospace; font-size: 10px; padding: 3mm; color: #000; }
              table { width: 100%; border-collapse: collapse; }
              th, td { padding: 1px 0; }
              .center { text-align: center; }
              .right { text-align: right; }
              h1, h2, p { margin: 1px 0; }
            </style>
          </head>
          <body>
            <h1 class="center">${escapeHtml(nombreEmpresa)}</h1>
            <p class="center">${escapeHtml(nitEmpresa)}</p>
            <p class="center">${escapeHtml(regimen)}</p>
            <p class="center">${escapeHtml(telefono)}</p>
            <p class="center">${escapeHtml(direccion)}</p>
            <p class="center">${escapeHtml(ciudad)}</p>
            <h2 class="center">${escapeHtml(tirilla.titulo)}</h2>
            <p class="center">${escapeHtml(rango)}</p>
            ${sinDocumentos}
            <p>${TICKET_SEPARATOR}</p><p>RESUMEN DE IVA</p><p>${TICKET_SEPARATOR}</p>
            <table><thead><tr><th>Tipo</th><th class="right">Compra</th><th class="right">Base</th><th class="right">IVA</th><th class="right">Desc</th></tr></thead><tbody>${ivaRows}</tbody></table>
            <p>TOTALES</p>
            <p>Compra: ${formatTicketMoney(tirilla.totales_iva.compra)}</p>
            <p>Base: ${formatTicketMoney(tirilla.totales_iva.base)}</p>
            <p>IVA: ${formatTicketMoney(tirilla.totales_iva.iva)}</p>
            <p>Descuentos: ${formatTicketMoney(tirilla.totales_iva.descuento)}</p>
            <p>${TICKET_SEPARATOR}</p><p>RESUMEN A CATEGORÍAS</p><p>${TICKET_SEPARATOR}</p>
            <table><thead><tr><th>Categoría</th><th class="right">Facturado</th></tr></thead><tbody>${categoriaRows}<tr><td>TOTAL</td><td class="right">${formatTicketMoney(tirilla.total_facturado)}</td></tr></tbody></table>
            <p>${TICKET_SEPARATOR}</p><p>RESUMEN A ESTADOS</p><p>${TICKET_SEPARATOR}</p>
            <table><thead><tr><th>${estadoTitulo}</th><th class="right">CANTIDAD</th></tr></thead><tbody>${estadoRows}</tbody></table>
            <p>${TICKET_SEPARATOR}</p><p>RESUMEN A MEDIO DE PAGO</p><p>${TICKET_SEPARATOR}</p>
            <table><thead><tr><th>${medioTitulo}</th><th>Medio Pago</th><th class="right">Facturado</th></tr></thead><tbody>${medioRows}<tr><td></td><td>TOTAL</td><td class="right">${formatTicketMoney(tirilla.total_facturado)}</td></tr></tbody></table>
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
