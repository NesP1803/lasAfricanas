import { useState } from 'react';
import EstadoDIANBadge from './EstadoDIANBadge';
import { facturacionApi, type EstadoDian, type FacturaElectronica } from '../services/facturacionApi';
import { useNotification } from '../../../contexts/NotificationContext';

interface FacturasTableProps {
  facturas: FacturaElectronica[];
  loading: boolean;
}

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const formatFecha = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return fecha;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'short', timeStyle: 'short' }).format(date);
};

export default function FacturasTable({ facturas, loading }: FacturasTableProps) {
  const [rowLoading, setRowLoading] = useState<Record<string, string | null>>({});
  const [estados, setEstados] = useState<Record<string, EstadoDian>>({});
  const { showNotification } = useNotification();

  const setActionLoading = (numero: string, action: string | null) => {
    setRowLoading((prev) => ({ ...prev, [numero]: action }));
  };

  const handleEstado = async (numero: string) => {
    setActionLoading(numero, 'estado');
    try {
      const data = await facturacionApi.getEstadoFactura(numero);
      setEstados((prev) => ({ ...prev, [numero]: data.estado }));
      showNotification({ message: `Estado DIAN consultado para factura ${numero}.`, type: 'info' });
    } catch {
      showNotification({ message: 'No fue posible consultar el estado DIAN.', type: 'error' });
    } finally {
      setActionLoading(numero, null);
    }
  };

  const handleDescargar = async (numero: string, tipo: 'xml' | 'pdf') => {
    setActionLoading(numero, tipo);
    try {
      if (tipo === 'xml') {
        await facturacionApi.descargarXML(numero);
      } else {
        await facturacionApi.descargarPDF(numero);
      }
    } catch {
      showNotification({
        message: `No fue posible descargar el archivo ${tipo.toUpperCase()} de la factura ${numero}.`,
        type: 'error',
      });
    } finally {
      setActionLoading(numero, null);
    }
  };

  const handleEnviarCorreo = async (numero: string) => {
    setActionLoading(numero, 'correo');
    try {
      await facturacionApi.enviarFacturaCorreo(numero);
      showNotification({ message: 'Factura enviada correctamente', type: 'success' });
    } catch {
      showNotification({ message: 'No fue posible enviar la factura por correo.', type: 'error' });
    } finally {
      setActionLoading(numero, null);
    }
  };

  if (loading) {
    return <div className="rounded-lg bg-white p-6 text-sm text-slate-500 shadow">Cargando facturas...</div>;
  }

  return (
    <div className="overflow-x-auto rounded-lg bg-white shadow">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-4 py-3">Número</th>
            <th className="px-4 py-3">Cliente</th>
            <th className="px-4 py-3">Fecha</th>
            <th className="px-4 py-3">Total</th>
            <th className="px-4 py-3">Estado DIAN</th>
            <th className="px-4 py-3">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {facturas.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                No hay facturas electrónicas disponibles.
              </td>
            </tr>
          ) : (
            facturas.map((factura) => {
              const loadingAction = rowLoading[factura.numero];
              const estadoActual = estados[factura.numero] ?? factura.estado_dian;
              return (
                <tr key={factura.numero} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800">{factura.numero}</td>
                  <td className="px-4 py-3 text-slate-700">{factura.cliente}</td>
                  <td className="px-4 py-3 text-slate-600">{formatFecha(factura.fecha)}</td>
                  <td className="px-4 py-3 text-slate-700">{currencyFormatter.format(factura.total)}</td>
                  <td className="px-4 py-3">
                    <EstadoDIANBadge estado={estadoActual} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleEstado(factura.numero)}
                        className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        Estado
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDescargar(factura.numero, 'xml')}
                        className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        XML
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDescargar(factura.numero, 'pdf')}
                        className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => handleEnviarCorreo(factura.numero)}
                        className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                        disabled={Boolean(loadingAction)}
                      >
                        Correo
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
