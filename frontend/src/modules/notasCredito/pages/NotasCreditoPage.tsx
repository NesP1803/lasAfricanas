import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotification } from '../../../contexts/NotificationContext';
import NotasCreditoTable from '../components/NotasCreditoTable';
import { notasCreditoApi, type NotaCredito } from '../services/notasCreditoApi';

export default function NotasCreditoPage() {
  const [notasCredito, setNotasCredito] = useState<NotaCredito[]>([]);
  const [loading, setLoading] = useState(false);
  const loadedOnceRef = useRef(false);
  const { showNotification } = useNotification();

  const cargarNotasCredito = useCallback(async () => {
    setLoading(true);
    try {
      const data = await notasCreditoApi.getNotasCredito();
      setNotasCredito(data);
    } catch {
      setNotasCredito([]);
      showNotification({ message: 'No fue posible cargar las notas crédito.', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [showNotification]);

  useEffect(() => {
    if (loadedOnceRef.current) return;
    loadedOnceRef.current = true;
    cargarNotasCredito();
  }, [cargarNotasCredito]);

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="rounded-lg bg-white p-5 shadow">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Facturación / Notas crédito</p>
            <h2 className="text-2xl font-semibold text-slate-800">Listado de notas crédito</h2>
            <p className="text-sm text-slate-500">Consulte estado Factus, correo, descargas y acciones operativas en un solo lugar.</p>
          </div>
          <Link to="/facturacion/nota-credito" className="inline-flex w-fit rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
            Crear nota crédito
          </Link>
        </div>
      </div>

      <NotasCreditoTable notasCredito={notasCredito} loading={loading} onRefresh={cargarNotasCredito} />
    </div>
  );
}
