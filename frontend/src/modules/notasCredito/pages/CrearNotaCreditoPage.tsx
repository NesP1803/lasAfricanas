import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import NotaCreditoForm from '../components/NotaCreditoForm';
import { notasCreditoApi, type CrearNotaCreditoPayload } from '../services/notasCreditoApi';
import { useNotification } from '../../../contexts/NotificationContext';

export default function CrearNotaCreditoPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { showNotification } = useNotification();

  const handleSubmit = async (payload: CrearNotaCreditoPayload) => {
    setLoading(true);
    try {
      await notasCreditoApi.crearNotaCredito(payload);
      showNotification({
        message: 'Nota crédito emitida correctamente.',
        type: 'success',
      });
      navigate('/notas-credito');
    } catch {
      showNotification({
        message: 'No fue posible emitir la nota crédito.',
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="rounded-lg bg-white p-4 shadow">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">Crear Nota Crédito</h2>
            <p className="text-sm text-slate-500">Diligencie los campos para emitir una nueva nota crédito.</p>
          </div>
          <Link to="/notas-credito" className="text-sm font-semibold text-blue-600 hover:text-blue-700">
            Volver al listado
          </Link>
        </div>
      </div>

      <NotaCreditoForm onSubmit={handleSubmit} loading={loading} />
    </div>
  );
}
