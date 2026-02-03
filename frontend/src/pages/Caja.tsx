import { useEffect, useState } from 'react';
import { ventasApi, type VentaListItem } from '../api/ventas';
import { useNotification } from '../contexts/NotificationContext';

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

export default function Caja() {
  const { showNotification } = useNotification();
  const [pendientes, setPendientes] = useState<VentaListItem[]>([]);
  const [cargando, setCargando] = useState(false);
  const [facturandoId, setFacturandoId] = useState<number | null>(null);

  const cargarPendientes = () => {
    setCargando(true);
    ventasApi
      .getPendientesCaja()
      .then((data) => setPendientes(data))
      .catch(() => setPendientes([]))
      .finally(() => setCargando(false));
  };

  useEffect(() => {
    cargarPendientes();
  }, []);

  const handleFacturar = async (ventaId: number) => {
    setFacturandoId(ventaId);
    try {
      const facturada = await ventasApi.facturarEnCaja(ventaId);
      showNotification({
        type: 'success',
        message: `Venta ${facturada.numero_comprobante ?? facturada.id} facturada.`,
      });
      cargarPendientes();
    } catch (error) {
      showNotification({
        type: 'error',
        message: 'No se pudo facturar la venta.',
      });
    } finally {
      setFacturandoId(null);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              Caja
            </p>
            <h2 className="text-lg font-semibold text-slate-900">
              Pendientes por facturar
            </h2>
          </div>
          <button
            type="button"
            onClick={cargarPendientes}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            Actualizar
          </button>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-100 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Documento</th>
                <th className="px-3 py-2">Cliente</th>
                <th className="px-3 py-2">Fecha</th>
                <th className="px-3 py-2 text-right">Total</th>
                <th className="px-3 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {cargando && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                    Cargando pendientes...
                  </td>
                </tr>
              )}
              {!cargando && pendientes.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                    No hay ventas pendientes.
                  </td>
                </tr>
              )}
              {pendientes.map((venta) => (
                <tr key={venta.id} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-semibold text-slate-700">
                    {venta.numero_comprobante || `#${venta.id}`}
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    {venta.cliente_nombre}
                  </td>
                  <td className="px-3 py-2 text-slate-500">
                    {new Date(venta.fecha).toLocaleString('es-CO')}
                  </td>
                  <td className="px-3 py-2 text-right font-semibold text-slate-700">
                    {currencyFormatter.format(Number(venta.total))}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleFacturar(venta.id)}
                      disabled={facturandoId === venta.id}
                      className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold uppercase text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {facturandoId === venta.id ? 'Facturando...' : 'Facturar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
