import { useState } from 'react';
import { useNotification } from '../../../contexts/NotificationContext';
import { notasCreditoApi, type EstadoDian, type NotaCredito } from '../services/notasCreditoApi';

interface NotasCreditoTableProps {
  notasCredito: NotaCredito[];
  loading: boolean;
}

const estadoStyles: Record<string, string> = {
  ACEPTADA: 'bg-emerald-100 text-emerald-700',
  RECHAZADA: 'bg-red-100 text-red-700',
  EN_PROCESO: 'bg-amber-100 text-amber-700',
  ERROR: 'bg-slate-200 text-slate-700',
};

const formatFecha = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return fecha;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'short', timeStyle: 'short' }).format(date);
};

function EstadoDianBadge({ estado }: { estado: EstadoDian }) {
  const normalizedEstado = estado?.toUpperCase() ?? 'ERROR';
  const style = estadoStyles[normalizedEstado] ?? estadoStyles.ERROR;

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>
      {normalizedEstado.replaceAll('_', ' ')}
    </span>
  );
}

export default function NotasCreditoTable({ notasCredito, loading }: NotasCreditoTableProps) {
  const [rowLoading, setRowLoading] = useState<Record<string, string | null>>({});
  const { showNotification } = useNotification();

  const handleDescargar = async (numero: string, tipo: 'xml' | 'pdf') => {
    setRowLoading((prev) => ({ ...prev, [numero]: tipo }));
    try {
      if (tipo === 'xml') {
        await notasCreditoApi.descargarXML(numero);
      } else {
        await notasCreditoApi.descargarPDF(numero);
      }
    } catch {
      showNotification({
        message: `No fue posible descargar ${tipo.toUpperCase()} de la nota crédito ${numero}.`,
        type: 'error',
      });
    } finally {
      setRowLoading((prev) => ({ ...prev, [numero]: null }));
    }
  };

  if (loading) {
    return <div className="rounded-lg bg-white p-6 text-sm text-slate-500 shadow">Cargando notas crédito...</div>;
  }

  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-4 py-3">Número</th>
            <th className="px-4 py-3">Factura asociada</th>
            <th className="px-4 py-3">Fecha</th>
            <th className="px-4 py-3">Motivo</th>
            <th className="px-4 py-3">Estado DIAN</th>
            <th className="px-4 py-3">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {notasCredito.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                No hay notas crédito registradas.
              </td>
            </tr>
          ) : (
            notasCredito.map((nota) => {
              const loadingAction = rowLoading[nota.numero];
              return (
                <tr key={nota.numero} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800">{nota.numero}</td>
                  <td className="px-4 py-3 text-slate-700">{nota.factura_asociada}</td>
                  <td className="px-4 py-3 text-slate-600">{formatFecha(nota.fecha)}</td>
                  <td className="px-4 py-3 text-slate-700">{nota.motivo}</td>
                  <td className="px-4 py-3">
                    <EstadoDianBadge estado={nota.estado_dian} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleDescargar(nota.numero, 'xml')}
                        className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        XML
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDescargar(nota.numero, 'pdf')}
                        className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        PDF
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
