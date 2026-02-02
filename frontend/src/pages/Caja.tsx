import { useEffect, useState } from 'react';
import { ventasApi, type Venta, type VentaListItem } from '../api/ventas';
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
  const [detalle, setDetalle] = useState<Venta | null>(null);
  const [cargando, setCargando] = useState(false);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const [cargandoFacturar, setCargandoFacturar] = useState(false);

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

  const handleSeleccionar = (ventaId: number) => {
    setCargandoDetalle(true);
    ventasApi
      .getVenta(ventaId)
      .then((data) => setDetalle(data))
      .catch(() => setDetalle(null))
      .finally(() => setCargandoDetalle(false));
  };

  const handleFacturar = async () => {
    if (!detalle) return;
    setCargandoFacturar(true);
    try {
      const facturada = await ventasApi.facturarEnCaja(detalle.id);
      showNotification({
        type: 'success',
        message: `Venta ${facturada.numero_comprobante ?? facturada.id} facturada.`,
      });
      setDetalle(facturada);
      cargarPendientes();
    } catch (error) {
      showNotification({
        type: 'error',
        message: 'No se pudo facturar la venta.',
      });
    } finally {
      setCargandoFacturar(false);
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
                      onClick={() => handleSeleccionar(venta.id)}
                      className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50"
                    >
                      Ver detalle
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              Detalle de venta
            </p>
            <h3 className="text-lg font-semibold text-slate-900">
              {detalle?.numero_comprobante || (detalle ? `Venta #${detalle.id}` : 'Selecciona una venta')}
            </h3>
          </div>
          <button
            type="button"
            onClick={handleFacturar}
            disabled={!detalle || cargandoFacturar}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {cargandoFacturar ? 'Facturando...' : 'Facturar'}
          </button>
        </div>
        {cargandoDetalle && (
          <p className="mt-4 text-sm text-slate-500">Cargando detalle...</p>
        )}
        {!cargandoDetalle && detalle && (
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
                <p className="text-xs text-slate-500">Cliente</p>
                <p className="font-semibold text-slate-700">
                  {detalle.cliente_info?.nombre ?? detalle.cliente}
                </p>
              </div>
              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
                <p className="text-xs text-slate-500">Total</p>
                <p className="font-semibold text-slate-700">
                  {currencyFormatter.format(Number(detalle.total))}
                </p>
              </div>
              <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
                <p className="text-xs text-slate-500">Estado</p>
                <p className="font-semibold text-slate-700">{detalle.estado_display}</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Producto</th>
                    <th className="px-3 py-2 text-right">Cantidad</th>
                    <th className="px-3 py-2 text-right">Precio</th>
                    <th className="px-3 py-2 text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.detalles.map((item) => (
                    <tr key={item.id} className="border-b border-slate-100">
                      <td className="px-3 py-2 text-slate-700">
                        {item.producto_nombre || item.producto}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {item.cantidad}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {currencyFormatter.format(Number(item.precio_unitario))}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold text-slate-700">
                        {currencyFormatter.format(Number(item.total))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {!cargandoDetalle && !detalle && (
          <p className="mt-4 text-sm text-slate-500">
            Selecciona una venta pendiente para visualizarla aquí.
          </p>
        )}
      </section>
    </div>
  );
}
