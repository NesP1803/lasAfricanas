import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useNotification } from '../../../contexts/NotificationContext';
import EstadoNotaCreditoBadge, { resolveEstadoNota } from '../components/EstadoNotaCreditoBadge';
import { notasCreditoApi, type NotaCredito } from '../services/notasCreditoApi';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

export default function DetalleNotaCreditoPage() {
  const { id } = useParams();
  const [nota, setNota] = useState<NotaCredito | null>(null);
  const [loading, setLoading] = useState(true);
  const { showNotification } = useNotification();

  useEffect(() => {
    const load = async () => {
      if (!id) return;
      setLoading(true);
      try {
        const data = await notasCreditoApi.getNotaCredito(Number(id));
        setNota(data);
      } catch {
        showNotification({ message: 'No fue posible cargar el detalle de la nota crédito.', type: 'error' });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, showNotification]);

  const resumen = useMemo(() => {
    const details = nota?.detalles || [];
    const subtotal = details.reduce((acc, line) => acc + Number(line.base_impuesto || 0), 0);
    const impuestos = details.reduce((acc, line) => acc + Number(line.impuesto || 0), 0);
    const total = details.reduce((acc, line) => acc + Number(line.total_linea || 0), 0);
    return { subtotal, impuestos, total, lineas: details.length, devuelveInventario: details.some((line) => line.afecta_inventario) };
  }, [nota]);

  if (loading) return <div className="px-6 py-6">Cargando detalle de nota crédito…</div>;
  if (!nota) return <div className="px-6 py-6">No se encontró la nota crédito solicitada.</div>;

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="rounded-xl bg-white p-5 shadow">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Notas crédito / Detalle</p>
            <h2 className="text-2xl font-semibold text-slate-900">Nota crédito {nota.numero}</h2>
            <p className="text-sm text-slate-500">Factura origen {nota.factura_asociada} · motivo: {nota.motivo}</p>
          </div>
          <div className="flex gap-2">
            <Link to="/listados/notas-credito" className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700">Volver</Link>
            <button type="button" onClick={() => notasCreditoApi.descargarPDF(nota.id, nota.numero)} className="rounded-md bg-violet-600 px-3 py-2 text-sm font-semibold text-white">PDF</button>
            <button type="button" onClick={() => notasCreditoApi.descargarXML(nota.id, nota.numero)} className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">XML</button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="space-y-4">
          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">Cabecera y estados</h3>
            <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
              <p><strong>Número:</strong> {nota.numero}</p>
              <p><strong>Factura origen:</strong> {nota.factura_asociada}</p>
              <p><strong>Tipo:</strong> {(nota.tipo_nota || 'PARCIAL').replaceAll('_', ' ')}</p>
              <p><strong>CUFE:</strong> {nota.cufe || 'No disponible'}</p>
              <p><strong>UUID:</strong> {nota.uuid || 'No disponible'}</p>
              <p><strong>Estado local / Factus:</strong> <EstadoNotaCreditoBadge estado={resolveEstadoNota(nota)} /></p>
              <p><strong>Correo:</strong> {nota.correo_enviado ? 'Enviado' : 'Pendiente'}</p>
            </div>
          </section>

          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">Productos acreditados</h3>
            <div className="mt-3 overflow-auto rounded-md border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Producto</th>
                    <th className="px-3 py-2">Cant. acreditada</th>
                    <th className="px-3 py-2">Precio unitario</th>
                    <th className="px-3 py-2">Impuesto</th>
                    <th className="px-3 py-2">Total línea</th>
                    <th className="px-3 py-2">Inventario</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(nota.detalles || []).map((linea) => (
                    <tr key={linea.id}>
                      <td className="px-3 py-2">{linea.producto_nombre}</td>
                      <td className="px-3 py-2">{linea.cantidad_a_acreditar}</td>
                      <td className="px-3 py-2">{money.format(Number(linea.precio_unitario || 0))}</td>
                      <td className="px-3 py-2">{money.format(Number(linea.impuesto || 0))}</td>
                      <td className="px-3 py-2">{money.format(Number(linea.total_linea || 0))}</td>
                      <td className="px-3 py-2">{linea.afecta_inventario ? 'Devuelve stock' : 'No afecta stock'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">Trazabilidad y observaciones</h3>
            <p className="mt-2 text-sm text-slate-700">Motivo: {nota.motivo}</p>
            {(nota.codigo_error || nota.mensaje_error) && (
              <details className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <summary className="cursor-pointer font-semibold">Ver detalle técnico</summary>
                <p className="mt-2"><strong>Código:</strong> {nota.codigo_error || 'N/D'}</p>
                <p><strong>Mensaje:</strong> {nota.mensaje_error || 'Sin mensaje'}</p>
              </details>
            )}
          </section>
        </div>

        <aside className="h-fit rounded-xl bg-white p-5 shadow">
          <h3 className="text-lg font-semibold text-slate-800">Resumen de impacto</h3>
          <div className="mt-3 space-y-2 text-sm text-slate-700">
            <p><strong>Subtotal:</strong> {money.format(resumen.subtotal)}</p>
            <p><strong>Impuestos:</strong> {money.format(resumen.impuestos)}</p>
            <p><strong>Total nota:</strong> {money.format(resumen.total)}</p>
            <p><strong>Líneas:</strong> {resumen.lineas}</p>
            <p><strong>Afecta inventario:</strong> {resumen.devuelveInventario ? 'Sí' : 'No'}</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
