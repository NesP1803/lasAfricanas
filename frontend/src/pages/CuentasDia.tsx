import { useEffect, useMemo, useState } from 'react';
import { FileText, Printer, ReceiptText } from 'lucide-react';
import { configuracionAPI } from '../api/configuracion';
import type { ConfiguracionEmpresa } from '../types';
import { ventasApi, type EstadisticasVentas, type VentaListItem } from '../api/ventas';

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
});

const toNumber = (value?: string | null) => (value ? Number(value) : 0);

const today = new Date().toISOString().split('T')[0];
const dateTimeFormatter = new Intl.DateTimeFormat('es-CO', {
  dateStyle: 'short',
  timeStyle: 'short',
});

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

  const getResumenVentas = async (
    tipoComprobante: 'FACTURA' | 'REMISION'
  ): Promise<{ ventas: VentaListItem[]; total: number }> => {
    const ventas = await ventasApi.getVentas({
      tipoComprobante,
      estado: 'CONFIRMADA',
      fechaInicio,
      fechaFin,
      ordering: '-fecha',
    });
    const total = ventas.reduce((acc, venta) => acc + toNumber(venta.total), 0);
    return { ventas, total };
  };

  const imprimirRecibo = async (
    tipo: 'FACTURAS' | 'REMISIONES',
    formato: 'POS' | 'CARTA'
  ) => {
    setPrinting(true);
    const titulo = tipo === 'FACTURAS' ? 'Recibo de facturas' : 'Recibo de remisiones';
    try {
      const tipoComprobante = tipo === 'FACTURAS' ? 'FACTURA' : 'REMISION';
      const { ventas, total } = await getResumenVentas(tipoComprobante);
      const printWindow = window.open('', '_blank', 'width=820,height=700');

      if (!printWindow) {
        setMensaje('No se pudo abrir la ventana de impresión.');
        return;
      }

      const nombreEmpresa = empresa?.razon_social || 'MOTOREPUESTOS LAS AFRICANAS';
      const nitEmpresa = empresa
        ? `${empresa.tipo_identificacion} ${empresa.identificacion}${empresa.dv ? `-${empresa.dv}` : ''}`
        : 'NIT 91.068.915-8';
      const direccionEmpresa = empresa
        ? `${empresa.direccion}, ${empresa.ciudad}`
        : 'Calle 6 # 12A-45 Gaira, Santa Marta';
      const telefonoEmpresa = empresa?.telefono ? `Tel: ${empresa.telefono}` : '';
      const rango = `${fechaInicio} a ${fechaFin}`;
      const conteo = ventas.length;
      const fechaImpresion = dateTimeFormatter.format(new Date());
      const filas = ventas
        .map((venta) => {
          const fecha = dateTimeFormatter.format(new Date(venta.fecha));
          return `
            <tr>
              <td>${venta.numero_comprobante}</td>
              <td>${fecha}</td>
              <td>${venta.medio_pago_display}</td>
              <td class="right">${currencyFormatter.format(toNumber(venta.total))}</td>
            </tr>
          `;
        })
        .join('');
      const detalleTabla =
        ventas.length > 0
          ? filas
          : `<tr><td colspan="4" class="empty">Sin documentos en el rango.</td></tr>`;

      const estilos =
        formato === 'POS'
          ? `
            body { font-family: Arial, sans-serif; padding: 16px; color: #0f172a; font-size: 11px; }
            h1 { font-size: 12px; text-transform: uppercase; margin: 0; }
            h2 { font-size: 11px; margin: 6px 0; text-transform: uppercase; }
            p { margin: 2px 0; }
            .box { border-top: 1px dashed #94a3b8; margin-top: 8px; padding-top: 8px; }
            .row { display: flex; justify-content: space-between; margin-bottom: 4px; }
            table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 10px; }
            th, td { padding: 4px 0; border-bottom: 1px dashed #cbd5f5; }
            th { text-align: left; text-transform: uppercase; font-size: 9px; color: #475569; }
            .right { text-align: right; }
            .empty { text-align: center; padding: 8px 0; color: #64748b; }
          `
          : `
            body { font-family: Arial, sans-serif; padding: 32px; color: #0f172a; font-size: 13px; }
            h1 { font-size: 18px; margin-bottom: 4px; }
            h2 { font-size: 16px; margin: 12px 0 6px; }
            p { margin: 2px 0; color: #475569; }
            .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
            .box { border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }
            .row { display: flex; justify-content: space-between; margin-bottom: 8px; }
            table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }
            th, td { padding: 8px 6px; border-bottom: 1px solid #e2e8f0; }
            th { text-align: left; text-transform: uppercase; font-size: 11px; color: #475569; }
            .right { text-align: right; }
            .empty { text-align: center; padding: 12px 0; color: #64748b; }
          `;

      printWindow.document.write(`
        <!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8" />
            <title>${titulo}</title>
            <style>${estilos}</style>
          </head>
          <body>
            <div class="${formato === 'POS' ? '' : 'header'}">
              <div>
                <h1>${nombreEmpresa}</h1>
                <p>${nitEmpresa}</p>
                <p>${direccionEmpresa}</p>
                ${telefonoEmpresa ? `<p>${telefonoEmpresa}</p>` : ''}
              </div>
              ${
                formato === 'CARTA'
                  ? `<div class="right"><p>${titulo}</p><p>${fechaImpresion}</p></div>`
                  : ''
              }
            </div>
            ${formato === 'POS' ? `<h2>${titulo}</h2>` : ''}
            <p>Rango: ${rango}</p>
            <p>Fecha impresión: ${fechaImpresion}</p>
            <div class="box">
              <div class="row">
                <span>Documentos</span>
                <span>${conteo}</span>
              </div>
              <div class="row">
                <span>Total</span>
                <span>${currencyFormatter.format(total)}</span>
              </div>
            </div>
            <h2>Detalle de documentos</h2>
            <table>
              <thead>
                <tr>
                  <th>No.</th>
                  <th>Fecha</th>
                  <th>Medio pago</th>
                  <th class="right">Total</th>
                </tr>
              </thead>
              <tbody>
                ${detalleTabla}
              </tbody>
            </table>
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
                  onClick={() => imprimirRecibo('FACTURAS', 'POS')}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading || printing}
                >
                  Tirilla
                  <Printer size={18} />
                </button>
                <button
                  type="button"
                  onClick={() => imprimirRecibo('FACTURAS', 'CARTA')}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading || printing}
                >
                  Carta
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
                  onClick={() => imprimirRecibo('REMISIONES', 'POS')}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading || printing}
                >
                  Tirilla
                  <Printer size={18} />
                </button>
                <button
                  type="button"
                  onClick={() => imprimirRecibo('REMISIONES', 'CARTA')}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading || printing}
                >
                  Carta
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
