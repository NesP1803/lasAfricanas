import { useEffect, useMemo, useState } from 'react';
import { CalendarRange, FileText, Printer, ReceiptText } from 'lucide-react';
import { ventasApi, type EstadisticasVentas } from '../api/ventas';

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
});

const toNumber = (value?: string | null) => (value ? Number(value) : 0);

const today = new Date().toISOString().split('T')[0];

export default function CuentasDia() {
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [stats, setStats] = useState<EstadisticasVentas | null>(null);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);

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
    cargarEstadisticas();
  }, []);

  const facturasValor = useMemo(
    () => toNumber(stats?.total_facturas_valor),
    [stats?.total_facturas_valor]
  );
  const remisionesValor = useMemo(
    () => toNumber(stats?.total_remisiones_valor),
    [stats?.total_remisiones_valor]
  );
  const totalCaja = facturasValor + remisionesValor;

  const imprimirRecibo = (tipo: 'FACTURAS' | 'REMISIONES') => {
    const total =
      tipo === 'FACTURAS' ? facturasValor : remisionesValor;
    const count =
      tipo === 'FACTURAS' ? stats?.total_facturas ?? 0 : stats?.total_remisiones ?? 0;
    const titulo =
      tipo === 'FACTURAS' ? 'Recibo de facturas' : 'Recibo de remisiones';
    const printWindow = window.open('', '_blank', 'width=420,height=600');

    if (!printWindow) {
      setMensaje('No se pudo abrir la ventana de impresión.');
      return;
    }

    printWindow.document.write(`
      <!doctype html>
      <html lang="es">
        <head>
          <meta charset="utf-8" />
          <title>${titulo}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 24px; color: #0f172a; }
            h1 { font-size: 18px; margin-bottom: 4px; }
            p { margin: 0 0 12px; color: #475569; }
            .box { border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }
            .row { display: flex; justify-content: space-between; margin-bottom: 8px; }
            .total { font-size: 20px; font-weight: bold; }
            .muted { color: #64748b; font-size: 12px; text-transform: uppercase; }
          </style>
        </head>
        <body>
          <h1>${titulo}</h1>
          <p>Rango: ${fechaInicio} a ${fechaFin}</p>
          <div class="box">
            <div class="row">
              <span class="muted">Documentos</span>
              <span>${count}</span>
            </div>
            <div class="row total">
              <span>Total</span>
              <span>${currencyFormatter.format(total)}</span>
            </div>
          </div>
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
    printWindow.close();
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
        <button
          type="button"
          onClick={cargarEstadisticas}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          disabled={loading}
        >
          <CalendarRange size={18} />
          {loading ? 'Calculando...' : 'Calcular'}
        </button>
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
            <button
              type="button"
              onClick={() => imprimirRecibo('FACTURAS')}
              className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Imprimir recibo facturas
              <Printer size={18} />
            </button>
            <button
              type="button"
              onClick={() => imprimirRecibo('REMISIONES')}
              className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Imprimir recibo remisiones
              <Printer size={18} />
            </button>
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
