import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotification } from '../../../contexts/NotificationContext';
import { notasCreditoApi, type NotaCredito } from '../services/notasCreditoApi';
import EstadoNotaCreditoBadge, { resolveEstadoNota } from './EstadoNotaCreditoBadge';

interface NotasCreditoTableProps {
  notasCredito: NotaCredito[];
  loading: boolean;
  onRefresh: () => Promise<void>;
}

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});

const formatFecha = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return fecha;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'short', timeStyle: 'short' }).format(date);
};

const getTotalNota = (nota: NotaCredito) =>
  (nota.detalles || []).reduce((acc, line) => acc + Number(line.total_linea || 0), 0);

export default function NotasCreditoTable({ notasCredito, loading, onRefresh }: NotasCreditoTableProps) {
  const [rowLoading, setRowLoading] = useState<Record<string, string | null>>({});
  const [query, setQuery] = useState('');
  const [estadoFilter, setEstadoFilter] = useState('TODOS');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const { showNotification } = useNotification();

  const filteredNotas = useMemo(() => {
    return notasCredito.filter((nota) => {
      const text = `${nota.numero} ${nota.factura_asociada} ${nota.motivo}`.toLowerCase();
      const q = query.trim().toLowerCase();
      const estado = resolveEstadoNota(nota);
      const fecha = new Date(nota.fecha).getTime();
      const desdeTime = desde ? new Date(`${desde}T00:00:00`).getTime() : null;
      const hastaTime = hasta ? new Date(`${hasta}T23:59:59`).getTime() : null;

      const matchQuery = !q || text.includes(q);
      const matchEstado = estadoFilter === 'TODOS' || estado === estadoFilter;
      const matchDesde = desdeTime === null || (!Number.isNaN(fecha) && fecha >= desdeTime);
      const matchHasta = hastaTime === null || (!Number.isNaN(fecha) && fecha <= hastaTime);
      return matchQuery && matchEstado && matchDesde && matchHasta;
    });
  }, [notasCredito, query, estadoFilter, desde, hasta]);

  const setActionLoading = (numero: string, action: string | null) => {
    setRowLoading((prev) => ({ ...prev, [numero]: action }));
  };

  const handleDescargar = async (nota: NotaCredito, tipo: 'xml' | 'pdf') => {
    setActionLoading(nota.numero, tipo);
    try {
      if (tipo === 'xml') await notasCreditoApi.descargarXML(nota.id, nota.numero);
      else await notasCreditoApi.descargarPDF(nota.id, nota.numero);
    } catch {
      showNotification({ message: `No fue posible descargar ${tipo.toUpperCase()} de ${nota.numero}. Intente sincronizar primero.`, type: 'error' });
    } finally {
      setActionLoading(nota.numero, null);
    }
  };

  const handleCorreo = async (nota: NotaCredito) => {
    setActionLoading(nota.numero, 'correo');
    try {
      await notasCreditoApi.enviarCorreo(nota.id);
      await onRefresh();
      showNotification({ message: `Correo enviado para ${nota.numero}.`, type: 'success' });
    } catch {
      showNotification({ message: 'No fue posible enviar correo de la nota crédito.', type: 'error' });
    } finally {
      setActionLoading(nota.numero, null);
    }
  };

  const handleEliminar = async (nota: NotaCredito) => {
    if (!window.confirm(`¿Eliminar la nota crédito ${nota.numero}? Esta acción no se puede deshacer.`)) return;
    setActionLoading(nota.numero, 'eliminar');
    try {
      await notasCreditoApi.eliminarNotaCredito(nota.id);
      await onRefresh();
      showNotification({ message: `Nota ${nota.numero} eliminada.`, type: 'success' });
    } catch {
      showNotification({ message: 'No fue posible eliminar la nota crédito.', type: 'error' });
    } finally {
      setActionLoading(nota.numero, null);
    }
  };

  if (loading) return <div className="rounded-lg bg-white p-6 text-sm text-slate-500 shadow">Cargando notas crédito...</div>;

  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-white p-4 shadow">
        <div className="grid gap-3 md:grid-cols-4">
          <input
            placeholder="Buscar por número, factura o motivo"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <select
            value={estadoFilter}
            onChange={(event) => setEstadoFilter(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="TODOS">Todos los estados</option>
            <option value="BORRADOR">Borrador</option>
            <option value="PENDIENTE_ENVIO">Pendiente envío</option>
            <option value="PENDIENTE_DIAN">Pendiente DIAN</option>
            <option value="CONFLICTO_FACTUS">Conflicto Factus</option>
            <option value="ACEPTADA">Aceptada</option>
            <option value="RECHAZADA">Rechazada</option>
            <option value="ERROR_INTEGRACION">Error integración</option>
          </select>
          <input type="date" value={desde} onChange={(event) => setDesde(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input type="date" value={hasta} onChange={(event) => setHasta(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg bg-white shadow">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
            <tr>
              <th className="px-4 py-3">Número</th>
              <th className="px-4 py-3">Factura</th>
              <th className="px-4 py-3">Cliente</th>
              <th className="px-4 py-3">Fecha</th>
              <th className="px-4 py-3">Tipo</th>
              <th className="px-4 py-3">Total acreditado</th>
              <th className="px-4 py-3">Estado de conciliación</th>
              <th className="px-4 py-3">Correo</th>
              <th className="px-4 py-3">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {filteredNotas.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-slate-500">No hay resultados para los filtros seleccionados.</td>
              </tr>
            ) : (
              filteredNotas.map((nota) => {
                const loadingAction = rowLoading[nota.numero];
                const total = getTotalNota(nota);
                const estado = resolveEstadoNota(nota);
                return (
                  <tr key={nota.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-semibold text-slate-800">{nota.numero}</td>
                    <td className="px-4 py-3 text-slate-700">{nota.factura_asociada}</td>
                    <td className="px-4 py-3 text-slate-700">—</td>
                    <td className="px-4 py-3 text-slate-600">{formatFecha(nota.fecha)}</td>
                    <td className="px-4 py-3 text-slate-700">{(nota.tipo_nota || 'PARCIAL').replaceAll('_', ' ')}</td>
                    <td className="px-4 py-3 text-slate-700">{currencyFormatter.format(total)}</td>
                    <td className="px-4 py-3">
                      <EstadoNotaCreditoBadge estado={estado} />
                      {Boolean(nota.estado_ui_mensaje) && (
                        <p className="mt-1 text-xs text-orange-700">
                          {nota.estado_ui_mensaje}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{nota.correo_enviado ? 'Enviado' : 'Pendiente'}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Link to={`/notas-credito/${nota.id}`} className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100">Ver</Link>
                        <button type="button" onClick={() => handleDescargar(nota, 'xml')} disabled={Boolean(loadingAction)} className="rounded-md bg-indigo-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60">XML</button>
                        <button type="button" onClick={() => handleDescargar(nota, 'pdf')} disabled={Boolean(loadingAction)} className="rounded-md bg-violet-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60">PDF</button>
                        <button type="button" onClick={() => handleCorreo(nota)} disabled={Boolean(loadingAction)} className="rounded-md bg-emerald-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60">Correo</button>
                        {(estado === 'BORRADOR' || estado.startsWith('ERROR') || estado === 'PENDIENTE_ENVIO') && (
                          <button type="button" onClick={() => handleEliminar(nota)} disabled={Boolean(loadingAction)} className="rounded-md bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60">Eliminar</button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
