import { useState } from 'react';
import { useNotification } from '../../../contexts/NotificationContext';
import { documentosSoporteApi, type DocumentoSoporte, type EstadoDian } from '../services/documentosSoporteApi';

interface DocumentosSoporteTableProps {
  documentos: DocumentoSoporte[];
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

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

function EstadoDianBadge({ estado }: { estado: EstadoDian }) {
  const normalizedEstado = estado?.toUpperCase() ?? 'ERROR';
  const style = estadoStyles[normalizedEstado] ?? estadoStyles.ERROR;

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>
      {normalizedEstado.replaceAll('_', ' ')}
    </span>
  );
}

const resolveEstadoDocumento = (documento: DocumentoSoporte): EstadoDian =>
  documento.estado ?? documento.estado_dian ?? 'ERROR';

export default function DocumentosSoporteTable({ documentos, loading }: DocumentosSoporteTableProps) {
  const [rowLoading, setRowLoading] = useState<Record<string, string | null>>({});
  const { showNotification } = useNotification();

  const handleDescargar = async (numero: string, tipo: 'xml' | 'pdf') => {
    setRowLoading((prev) => ({ ...prev, [numero]: tipo }));
    try {
      if (tipo === 'xml') {
        await documentosSoporteApi.descargarXML(numero);
      } else {
        await documentosSoporteApi.descargarPDF(numero);
      }
    } catch {
      showNotification({
        message: `No fue posible descargar ${tipo.toUpperCase()} del documento soporte ${numero}.`,
        type: 'error',
      });
    } finally {
      setRowLoading((prev) => ({ ...prev, [numero]: null }));
    }
  };

  if (loading) {
    return <div className="rounded-lg bg-white p-6 text-sm text-slate-500 shadow">Cargando documentos soporte...</div>;
  }

  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-4 py-3">Número</th>
            <th className="px-4 py-3">Proveedor</th>
            <th className="px-4 py-3">Documento proveedor</th>
            <th className="px-4 py-3">Fecha</th>
            <th className="px-4 py-3">Total</th>
            <th className="px-4 py-3">Estado DIAN</th>
            <th className="px-4 py-3">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {documentos.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                No hay documentos soporte registrados.
              </td>
            </tr>
          ) : (
            documentos.map((documento) => {
              const loadingAction = rowLoading[documento.numero];
              return (
                <tr key={documento.numero} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800">{documento.numero}</td>
                  <td className="px-4 py-3 text-slate-700">{documento.proveedor_nombre}</td>
                  <td className="px-4 py-3 text-slate-700">{documento.proveedor_documento}</td>
                  <td className="px-4 py-3 text-slate-600">{formatFecha(documento.fecha)}</td>
                  <td className="px-4 py-3 text-slate-700">{currencyFormatter.format(documento.total)}</td>
                  <td className="px-4 py-3">
                    <EstadoDianBadge estado={resolveEstadoDocumento(documento)} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleDescargar(documento.numero, 'xml')}
                        className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        XML
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDescargar(documento.numero, 'pdf')}
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
