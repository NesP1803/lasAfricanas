import { useEffect, useMemo, useState } from 'react';
import {
  Banknote,
  CheckCircle,
  CreditCard,
  DollarSign,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import {
  ventasApi,
  cajasApi,
  type Caja as CajaType,
  type VentaPendienteCaja,
  type EstadisticasCaja,
} from '../api/ventas';
import { useAuth } from '../contexts/AuthContext';
import { useNotification } from '../contexts/NotificationContext';

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const roundCop = (value: number) => Math.round(value);

export default function Caja() {
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const [cajas, setCajas] = useState<CajaType[]>([]);
  const [cajaSeleccionada, setCajaSeleccionada] = useState<number | null>(null);
  const [ventasPendientes, setVentasPendientes] = useState<VentaPendienteCaja[]>([]);
  const [estadisticas, setEstadisticas] = useState<EstadisticasCaja | null>(null);
  const [cargando, setCargando] = useState(false);
  const [ventaSeleccionada, setVentaSeleccionada] = useState<VentaPendienteCaja | null>(null);
  const [mostrarModalPago, setMostrarModalPago] = useState(false);
  const [medioPago, setMedioPago] = useState<'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO'>('EFECTIVO');
  const [efectivoRecibido, setEfectivoRecibido] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [procesando, setProcesando] = useState(false);
  const [busqueda, setBusqueda] = useState('');

  // Cargar cajas disponibles
  useEffect(() => {
    cajasApi.getCajas()
      .then((data) => {
        setCajas(data.filter(c => c.is_active));
        // Si el usuario tiene caja asignada, seleccionarla automáticamente
        if (user?.caja) {
          setCajaSeleccionada(user.caja);
        } else if (data.length === 1) {
          setCajaSeleccionada(data[0].id);
        }
      })
      .catch(() => {
        showNotification({
          type: 'error',
          message: 'Error al cargar las cajas',
        });
      });
  }, [user?.caja, showNotification]);

  // Cargar ventas pendientes cuando se selecciona una caja
  useEffect(() => {
    if (!cajaSeleccionada) return;

    const cargarDatos = async () => {
      setCargando(true);
      try {
        const [ventas, stats] = await Promise.all([
          cajasApi.getVentasPendientes(cajaSeleccionada),
          cajasApi.getEstadisticas(cajaSeleccionada),
        ]);
        setVentasPendientes(ventas);
        setEstadisticas(stats);
      } catch {
        showNotification({
          type: 'error',
          message: 'Error al cargar datos de la caja',
        });
      } finally {
        setCargando(false);
      }
    };

    cargarDatos();
    // Actualizar cada 30 segundos
    const interval = setInterval(cargarDatos, 30000);
    return () => clearInterval(interval);
  }, [cajaSeleccionada, showNotification]);

  const ventasFiltradas = useMemo(() => {
    if (!busqueda.trim()) return ventasPendientes;
    const termino = busqueda.toLowerCase();
    return ventasPendientes.filter(
      (v) =>
        v.numero_comprobante.toLowerCase().includes(termino) ||
        v.cliente_nombre.toLowerCase().includes(termino) ||
        v.cliente_numero_documento.includes(termino)
    );
  }, [ventasPendientes, busqueda]);

  const totalVenta = useMemo(() => {
    if (!ventaSeleccionada) return 0;
    return Number(ventaSeleccionada.total);
  }, [ventaSeleccionada]);

  const cambio = useMemo(() => {
    if (medioPago !== 'EFECTIVO') return 0;
    const recibido = Number(efectivoRecibido.replace(/[^\d.-]/g, '')) || 0;
    return Math.max(0, recibido - totalVenta);
  }, [efectivoRecibido, totalVenta, medioPago]);

  const handleSeleccionarVenta = (venta: VentaPendienteCaja) => {
    setVentaSeleccionada(venta);
    setMostrarModalPago(true);
    setMedioPago('EFECTIVO');
    setEfectivoRecibido('');
    setObservaciones('');
  };

  const handleProcesarPago = async () => {
    if (!ventaSeleccionada) return;

    if (medioPago === 'EFECTIVO') {
      const recibido = Number(efectivoRecibido.replace(/[^\d.-]/g, '')) || 0;
      if (recibido < totalVenta) {
        showNotification({
          type: 'error',
          message: 'El efectivo recibido debe ser mayor o igual al total',
        });
        return;
      }
    }

    setProcesando(true);
    try {
      await ventasApi.procesarPago(ventaSeleccionada.id, {
        medio_pago: medioPago,
        efectivo_recibido: medioPago === 'EFECTIVO'
          ? Number(efectivoRecibido.replace(/[^\d.-]/g, '')) || 0
          : 0,
        observaciones,
      });

      showNotification({
        type: 'success',
        message: `Pago procesado correctamente. ${medioPago === 'EFECTIVO' ? `Cambio: ${currencyFormatter.format(cambio)}` : ''}`,
      });

      // Actualizar lista
      setVentasPendientes((prev) =>
        prev.filter((v) => v.id !== ventaSeleccionada.id)
      );
      if (cajaSeleccionada) {
        cajasApi.getEstadisticas(cajaSeleccionada).then(setEstadisticas);
      }
      setMostrarModalPago(false);
      setVentaSeleccionada(null);
    } catch (error) {
      showNotification({
        type: 'error',
        message: error instanceof Error ? error.message : 'Error al procesar pago',
      });
    } finally {
      setProcesando(false);
    }
  };

  const handleActualizar = async () => {
    if (!cajaSeleccionada) return;
    setCargando(true);
    try {
      const [ventas, stats] = await Promise.all([
        cajasApi.getVentasPendientes(cajaSeleccionada),
        cajasApi.getEstadisticas(cajaSeleccionada),
      ]);
      setVentasPendientes(ventas);
      setEstadisticas(stats);
      showNotification({
        type: 'success',
        message: 'Datos actualizados',
      });
    } catch {
      showNotification({
        type: 'error',
        message: 'Error al actualizar',
      });
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Selector de caja y estadísticas */}
      <section className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Caja
              </label>
              <select
                value={cajaSeleccionada ?? ''}
                onChange={(e) => setCajaSeleccionada(Number(e.target.value) || null)}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              >
                <option value="">Seleccionar caja</option>
                {cajas.map((caja) => (
                  <option key={caja.id} value={caja.id}>
                    {caja.nombre} {caja.ubicacion ? `(${caja.ubicacion})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={handleActualizar}
              disabled={!cajaSeleccionada || cargando}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw size={16} className={cargando ? 'animate-spin' : ''} />
              Actualizar
            </button>
          </div>

          {estadisticas && (
            <div className="flex items-center gap-6">
              <div className="text-center">
                <p className="text-[10px] font-semibold uppercase text-slate-500">Pendientes</p>
                <p className="text-lg font-bold text-amber-600">
                  {estadisticas.pendientes.cantidad}
                </p>
              </div>
              <div className="text-center">
                <p className="text-[10px] font-semibold uppercase text-slate-500">Por cobrar</p>
                <p className="text-lg font-bold text-slate-800">
                  {currencyFormatter.format(estadisticas.pendientes.total)}
                </p>
              </div>
              <div className="text-center">
                <p className="text-[10px] font-semibold uppercase text-slate-500">Cobrado hoy</p>
                <p className="text-lg font-bold text-emerald-600">
                  {currencyFormatter.format(estadisticas.cobradas_hoy.total)}
                </p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Barra de búsqueda */}
      {cajaSeleccionada && (
        <section className="rounded-2xl border border-slate-200 bg-white px-5 py-3 shadow-sm">
          <div className="flex items-center gap-3">
            <Search size={18} className="text-slate-400" />
            <input
              type="text"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar por número, cliente o documento..."
              className="flex-1 bg-transparent text-sm focus:outline-none"
            />
            {busqueda && (
              <button
                type="button"
                onClick={() => setBusqueda('')}
                className="text-slate-400 hover:text-slate-600"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </section>
      )}

      {/* Lista de ventas pendientes */}
      {cajaSeleccionada ? (
        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 bg-amber-50 px-5 py-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
              Ventas pendientes de cobro ({ventasFiltradas.length})
            </h2>
          </div>

          {cargando ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw size={24} className="animate-spin text-slate-400" />
            </div>
          ) : ventasFiltradas.length === 0 ? (
            <div className="py-12 text-center text-slate-500">
              {busqueda ? 'No hay resultados para la búsqueda' : 'No hay ventas pendientes de cobro'}
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {ventasFiltradas.map((venta) => (
                <div
                  key={venta.id}
                  className="flex items-center justify-between px-5 py-4 hover:bg-slate-50"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100 text-amber-600">
                      <DollarSign size={20} />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-800">
                        {venta.numero_comprobante}
                      </p>
                      <p className="text-sm text-slate-500">
                        {venta.cliente_nombre} · {venta.cliente_numero_documento}
                      </p>
                      <p className="text-xs text-slate-400">
                        Vendedor: {venta.vendedor_nombre} · {new Date(venta.fecha).toLocaleString('es-CO')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-lg font-bold text-slate-800">
                        {currencyFormatter.format(Number(venta.total))}
                      </p>
                      <p className="text-xs text-slate-500">
                        {venta.tipo_comprobante_display}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleSeleccionarVenta(venta)}
                      className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
                    >
                      <Banknote size={16} />
                      Cobrar
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="rounded-2xl border border-slate-200 bg-white px-5 py-12 text-center shadow-sm">
          <DollarSign size={48} className="mx-auto text-slate-300" />
          <p className="mt-4 text-slate-500">
            Selecciona una caja para ver las ventas pendientes de cobro
          </p>
        </section>
      )}

      {/* Modal de procesamiento de pago */}
      {mostrarModalPago && ventaSeleccionada && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-slate-500">
                  Procesar pago
                </p>
                <h3 className="text-lg font-semibold text-slate-900">
                  {ventaSeleccionada.numero_comprobante}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setMostrarModalPago(false)}
                className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-6 px-6 py-4">
              {/* Información del cliente */}
              <div className="rounded-lg bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-700">
                  {ventaSeleccionada.cliente_nombre}
                </p>
                <p className="text-sm text-slate-500">
                  {ventaSeleccionada.cliente_numero_documento}
                </p>
              </div>

              {/* Resumen de productos */}
              <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2 text-left">Producto</th>
                      <th className="px-3 py-2 text-right">Cant</th>
                      <th className="px-3 py-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {ventaSeleccionada.detalles.map((detalle, idx) => (
                      <tr key={idx}>
                        <td className="px-3 py-2 text-slate-700">
                          {detalle.producto_nombre || `Producto ${detalle.producto}`}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {detalle.cantidad}
                        </td>
                        <td className="px-3 py-2 text-right font-medium text-slate-800">
                          {currencyFormatter.format(Number(detalle.total))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totales */}
              <div className="space-y-2 rounded-lg bg-amber-50 p-4">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">Subtotal</span>
                  <span className="font-medium">{currencyFormatter.format(Number(ventaSeleccionada.subtotal))}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-600">IVA</span>
                  <span className="font-medium">{currencyFormatter.format(Number(ventaSeleccionada.iva))}</span>
                </div>
                {Number(ventaSeleccionada.descuento_valor) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Descuento</span>
                    <span className="font-medium text-rose-600">
                      -{currencyFormatter.format(Number(ventaSeleccionada.descuento_valor))}
                    </span>
                  </div>
                )}
                <div className="flex justify-between border-t border-amber-200 pt-2 text-lg font-bold">
                  <span className="text-slate-800">Total a cobrar</span>
                  <span className="text-emerald-600">
                    {currencyFormatter.format(totalVenta)}
                  </span>
                </div>
              </div>

              {/* Método de pago */}
              <div className="space-y-3">
                <label className="text-xs font-semibold uppercase text-slate-500">
                  Método de pago
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { value: 'EFECTIVO', label: 'Efectivo', icon: Banknote },
                    { value: 'TARJETA', label: 'Tarjeta', icon: CreditCard },
                    { value: 'TRANSFERENCIA', label: 'Transfer.', icon: DollarSign },
                    { value: 'CREDITO', label: 'Crédito', icon: DollarSign },
                  ].map(({ value, label, icon: Icon }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setMedioPago(value as typeof medioPago)}
                      className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-xs font-medium transition ${
                        medioPago === value
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <Icon size={20} />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Campo de efectivo recibido */}
              {medioPago === 'EFECTIVO' && (
                <div className="space-y-3">
                  <label className="text-xs font-semibold uppercase text-slate-500">
                    Efectivo recibido
                  </label>
                  <input
                    type="text"
                    value={efectivoRecibido}
                    onChange={(e) => setEfectivoRecibido(e.target.value)}
                    placeholder="0"
                    className="w-full rounded-lg border border-slate-200 px-4 py-3 text-lg font-semibold focus:border-blue-500 focus:outline-none"
                    autoFocus
                  />
                  {cambio > 0 && (
                    <div className="flex items-center justify-between rounded-lg bg-blue-50 p-3">
                      <span className="text-sm font-medium text-blue-700">Cambio a devolver:</span>
                      <span className="text-lg font-bold text-blue-700">
                        {currencyFormatter.format(roundCop(cambio))}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Observaciones */}
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-slate-500">
                  Observaciones (opcional)
                </label>
                <textarea
                  value={observaciones}
                  onChange={(e) => setObservaciones(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                  placeholder="Notas adicionales..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
              <button
                type="button"
                onClick={() => setMostrarModalPago(false)}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleProcesarPago}
                disabled={procesando}
                className="flex items-center gap-2 rounded-lg bg-emerald-600 px-6 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {procesando ? (
                  <RefreshCw size={16} className="animate-spin" />
                ) : (
                  <CheckCircle size={16} />
                )}
                Confirmar pago
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
