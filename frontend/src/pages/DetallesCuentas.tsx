import { useCallback, useEffect, useMemo, useState } from 'react';
import { CalendarRange, FileText, ReceiptText } from 'lucide-react';
import { ventasApi, type EstadisticasVentas } from '../api/ventas';

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const toNumber = (value?: string | null) => (value ? Number(value) : 0);

const today = new Date().toISOString().split('T')[0];

export default function DetallesCuentas() {
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [stats, setStats] = useState<EstadisticasVentas | null>(null);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const cargarEstadisticas = useCallback(async () => {
    setLoading(true);
    try {
      const response = await ventasApi.getEstadisticas({
        fechaInicio,
        fechaFin,
      });
      setStats(response);
      setMensaje(null);
    } catch (error) {
      setMensaje('No se pudo cargar el detalle de cuentas. Intenta más tarde.');
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [fechaInicio, fechaFin]);

  useEffect(() => {
    if (!fechaInicio || !fechaFin) {
      return;
    }
    cargarEstadisticas();
  }, [cargarEstadisticas, fechaInicio, fechaFin]);

  const facturasValor = useMemo(
    () => toNumber(stats?.total_facturas_valor),
    [stats?.total_facturas_valor]
  );
  const remisionesValor = useMemo(
    () => toNumber(stats?.total_remisiones_valor),
    [stats?.total_remisiones_valor]
  );
  const totalCaja = facturasValor + remisionesValor;
  const facturasPorEmpleado = stats?.facturas_por_usuario ?? [];
  const remisionesPorEmpleado = stats?.remisiones_por_usuario ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Detalles de las cuentas
          </h1>
          <p className="text-sm text-slate-500">
            Visualiza lo recaudado en facturas y remisiones con el rango de fechas.
          </p>
        </div>
      </div>

      <section className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:grid-cols-[1.4fr,1fr]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="min-w-[180px] space-y-2">
              <label className="text-xs font-semibold uppercase text-slate-500">
                Fecha inicio
              </label>
              <input
                type="date"
                value={fechaInicio}
                onChange={(event) => setFechaInicio(event.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="min-w-[180px] space-y-2">
              <label className="text-xs font-semibold uppercase text-slate-500">
                Fecha final
              </label>
              <input
                type="date"
                value={fechaFin}
                onChange={(event) => setFechaFin(event.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="ml-auto flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
              <CalendarRange size={14} />
              {fechaInicio} → {fechaFin}
              {loading && <span className="text-blue-600">Calculando…</span>}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">
                    Información de la facturación
                  </p>
                  <p className="text-base font-semibold text-slate-900">
                    Documentos de facturas
                  </p>
                </div>
                <FileText className="text-blue-600" size={24} />
              </div>
              <div className="mt-4 grid gap-3 text-sm text-slate-600">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Documentos facturados</span>
                  <span className="font-semibold text-slate-900">
                    {stats?.total_facturas ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Documentos anulados</span>
                  <span className="font-semibold text-slate-900">0</span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Pagadas en efectivo</span>
                  <span className="font-semibold text-slate-900">
                    {stats?.total_facturas ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Pagadas con tarjeta</span>
                  <span className="font-semibold text-slate-900">0</span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Recaudado en efectivo</span>
                  <span className="font-semibold text-slate-900">
                    {currencyFormatter.format(facturasValor)}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Recaudado con tarjetas</span>
                  <span className="font-semibold text-slate-900">
                    {currencyFormatter.format(0)}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2 text-base font-semibold text-slate-900">
                  <span>Total recaudado en facturas</span>
                  <span>{currencyFormatter.format(facturasValor)}</span>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">
                    Información de las remisiones
                  </p>
                  <p className="text-base font-semibold text-slate-900">
                    Documentos de remisiones
                  </p>
                </div>
                <ReceiptText className="text-amber-500" size={24} />
              </div>
              <div className="mt-4 grid gap-3 text-sm text-slate-600">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Remisiones facturadas</span>
                  <span className="font-semibold text-slate-900">
                    {stats?.total_remisiones ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Remisiones anuladas</span>
                  <span className="font-semibold text-slate-900">0</span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Pagadas en efectivo</span>
                  <span className="font-semibold text-slate-900">
                    {stats?.total_remisiones ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Pagadas con tarjeta</span>
                  <span className="font-semibold text-slate-900">0</span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Recaudado en efectivo</span>
                  <span className="font-semibold text-slate-900">
                    {currencyFormatter.format(remisionesValor)}
                  </span>
                </div>
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span>Recaudado con tarjetas</span>
                  <span className="font-semibold text-slate-900">
                    {currencyFormatter.format(0)}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2 text-base font-semibold text-slate-900">
                  <span>Total recaudado en remisiones</span>
                  <span>{currencyFormatter.format(remisionesValor)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase text-slate-500">
              Cuadre de facturas por empleados
            </p>
            <div className="mt-3 overflow-hidden rounded-xl border border-slate-200">
              <div className="grid grid-cols-2 bg-amber-100 text-xs font-semibold uppercase text-slate-600">
                <span className="px-3 py-2">Usuario</span>
                <span className="px-3 py-2 text-right">Cuentas</span>
              </div>
              {facturasPorEmpleado.length === 0 ? (
                <div className="px-3 py-4 text-center text-sm text-slate-400">
                  Sin datos por empleado.
                </div>
              ) : (
                facturasPorEmpleado.map((item) => (
                  <div
                    key={item.usuario}
                    className="grid grid-cols-2 border-t border-slate-100 text-sm text-slate-600"
                  >
                    <span className="px-3 py-2">{item.usuario}</span>
                    <span className="px-3 py-2 text-right font-semibold text-slate-900">
                      {item.cuentas}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase text-slate-500">
              Cuadre de remisiones por empleados
            </p>
            <div className="mt-3 overflow-hidden rounded-xl border border-slate-200">
              <div className="grid grid-cols-2 bg-amber-100 text-xs font-semibold uppercase text-slate-600">
                <span className="px-3 py-2">Usuario</span>
                <span className="px-3 py-2 text-right">Cuentas</span>
              </div>
              {remisionesPorEmpleado.length === 0 ? (
                <div className="px-3 py-4 text-center text-sm text-slate-400">
                  Sin datos por empleado.
                </div>
              ) : (
                remisionesPorEmpleado.map((item) => (
                  <div
                    key={item.usuario}
                    className="grid grid-cols-2 border-t border-slate-100 text-sm text-slate-600"
                  >
                    <span className="px-3 py-2">{item.usuario}</span>
                    <span className="px-3 py-2 text-right font-semibold text-slate-900">
                      {item.cuentas}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <p className="text-xs font-semibold uppercase text-slate-500">
          Dinero en caja - cuentas totales
        </p>
        <p className="mt-3 text-4xl font-bold text-slate-900">
          {currencyFormatter.format(totalCaja)}
        </p>
      </section>

      {mensaje && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {mensaje}
        </div>
      )}
    </div>
  );
}
