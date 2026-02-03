import { useEffect, useMemo, useState } from 'react';
import { Printer, X } from 'lucide-react';
import { configuracionAPI } from '../api/configuracion';
import { ventasApi, type Venta, type VentaListItem } from '../api/ventas';
import ComprobanteTemplate from '../components/ComprobanteTemplate';
import { useNotification } from '../contexts/NotificationContext';
import type { ConfiguracionEmpresa, ConfiguracionFacturacion } from '../types';
import { printComprobante } from '../utils/printComprobante';

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
  const [documento, setDocumento] = useState<Venta | null>(null);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa | null>(null);
  const [facturacion, setFacturacion] = useState<ConfiguracionFacturacion | null>(null);

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

  useEffect(() => {
    configuracionAPI
      .obtenerEmpresa()
      .then(setEmpresa)
      .catch(() => setEmpresa(null));
    configuracionAPI
      .obtenerFacturacion()
      .then(setFacturacion)
      .catch(() => setFacturacion(null));
  }, []);

  const handleFacturar = async (ventaId: number) => {
    setFacturandoId(ventaId);
    try {
      const facturada = await ventasApi.facturarEnCaja(ventaId);
      showNotification({
        type: 'success',
        message: `Venta ${facturada.numero_comprobante ?? facturada.id} facturada.`,
      });
      setDocumento(facturada);
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

  const detallesDocumento = useMemo(() => {
    if (!documento?.detalles?.length) return [];
    return documento.detalles.map((detalle) => ({
      descripcion: detalle.producto_nombre ?? 'Producto',
      codigo: detalle.producto_codigo ?? '',
      cantidad: Number(detalle.cantidad),
      precioUnitario: Number(detalle.precio_unitario),
      descuento: Number(detalle.descuento_unitario),
      ivaPorcentaje: Number(detalle.iva_porcentaje),
      total: Number(detalle.total),
    }));
  }, [documento]);

  const handleImprimir = () => {
    if (!documento) return;
    printComprobante({
      tipo: documento.tipo_comprobante as 'FACTURA' | 'REMISION' | 'COTIZACION',
      numero: documento.numero_comprobante || `#${documento.id}`,
      fecha: documento.facturada_at || documento.fecha,
      clienteNombre: documento.cliente_info?.nombre ?? 'Cliente general',
      clienteDocumento: documento.cliente_info?.numero_documento ?? '',
      medioPago: documento.medio_pago_display ?? documento.medio_pago,
      estado: documento.estado_display ?? documento.estado,
      detalles: detallesDocumento,
      subtotal: Number(documento.subtotal),
      descuento: Number(documento.descuento_valor),
      iva: Number(documento.iva),
      total: Number(documento.total),
      efectivoRecibido:
        documento.efectivo_recibido !== undefined && documento.efectivo_recibido !== null
          ? Number(documento.efectivo_recibido)
          : undefined,
      cambio:
        documento.cambio !== undefined && documento.cambio !== null
          ? Number(documento.cambio)
          : undefined,
      notas: facturacion?.notas_factura,
      resolucion: facturacion?.resolucion,
      empresa,
    });
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

      {documento && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4">
          <div className="relative w-full max-w-5xl rounded-lg bg-white p-6 shadow-xl">
            <button
              type="button"
              className="absolute right-4 top-4 text-slate-500 hover:text-slate-700"
              onClick={() => setDocumento(null)}
            >
              <X size={20} />
            </button>
            <div className="space-y-4">
              <div className="text-center">
                <p className="text-xs uppercase text-slate-500">Documento generado</p>
                <h3 className="text-lg font-semibold text-slate-800">
                  {documento.tipo_comprobante_display}
                </h3>
              </div>
              <div className="max-h-[70vh] overflow-auto rounded border border-slate-200 bg-slate-50 p-4">
                <ComprobanteTemplate
                  tipo={documento.tipo_comprobante as 'FACTURA' | 'REMISION' | 'COTIZACION'}
                  numero={documento.numero_comprobante || `#${documento.id}`}
                  fecha={documento.facturada_at || documento.fecha}
                  clienteNombre={documento.cliente_info?.nombre ?? 'Cliente general'}
                  clienteDocumento={documento.cliente_info?.numero_documento ?? ''}
                  medioPago={documento.medio_pago_display ?? documento.medio_pago}
                  estado={documento.estado_display ?? documento.estado}
                  detalles={detallesDocumento}
                  subtotal={Number(documento.subtotal)}
                  descuento={Number(documento.descuento_valor)}
                  iva={Number(documento.iva)}
                  total={Number(documento.total)}
                  efectivoRecibido={
                    documento.efectivo_recibido !== undefined &&
                    documento.efectivo_recibido !== null
                      ? Number(documento.efectivo_recibido)
                      : undefined
                  }
                  cambio={
                    documento.cambio !== undefined && documento.cambio !== null
                      ? Number(documento.cambio)
                      : undefined
                  }
                  notas={facturacion?.notas_factura}
                  resolucion={facturacion?.resolucion}
                  empresa={empresa}
                />
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={handleImprimir}
                  className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
                >
                  <Printer size={16} />
                  Imprimir
                </button>
                <button
                  type="button"
                  onClick={() => setDocumento(null)}
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600"
                >
                  Cerrar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
