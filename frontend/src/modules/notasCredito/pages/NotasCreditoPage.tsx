import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotification } from '../../../contexts/NotificationContext';
import NotasCreditoTable from '../components/NotasCreditoTable';
import { notasCreditoApi, type NotaCredito } from '../services/notasCreditoApi';

export default function NotasCreditoPage() {
  const [notasCredito, setNotasCredito] = useState<NotaCredito[]>([]);
  const [loading, setLoading] = useState(false);
  const { showNotification } = useNotification();

  useEffect(() => {
    const cargarNotasCredito = async () => {
      setLoading(true);
      try {
        const data = await notasCreditoApi.getNotasCredito();
        setNotasCredito(data);
      } catch {
        setNotasCredito([]);
        showNotification({
          message: 'No fue posible cargar las notas crédito.',
          type: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    cargarNotasCredito();
  }, [showNotification]);

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="flex flex-col gap-3 rounded-lg bg-white p-4 shadow sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Notas Crédito</h2>
          <p className="text-sm text-slate-500">Visualice, gestione y descargue XML/PDF de notas crédito emitidas.</p>
        </div>
        <Link
          to="/notas-credito/crear"
          className="inline-flex w-fit rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Crear nota crédito
        </Link>
      </div>

      <NotasCreditoTable notasCredito={notasCredito} loading={loading} />
    </div>
  );
}
