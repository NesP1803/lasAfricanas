import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useNotification } from '../../../contexts/NotificationContext';
import DocumentoSoporteForm from '../components/DocumentoSoporteForm';
import { documentosSoporteApi, type CrearDocumentoSoportePayload } from '../services/documentosSoporteApi';

export default function CrearDocumentoSoportePage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { showNotification } = useNotification();

  const handleSubmit = async (payload: CrearDocumentoSoportePayload) => {
    setLoading(true);
    try {
      await documentosSoporteApi.crearDocumentoSoporte(payload);
      showNotification({
        message: 'Documento soporte emitido correctamente.',
        type: 'success',
      });
      navigate('/listados/documentos-soporte');
    } catch {
      showNotification({
        message: 'No fue posible emitir el documento soporte.',
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
            <h2 className="text-xl font-semibold text-slate-800">Crear Documento Soporte</h2>
            <p className="text-sm text-slate-500">
              Registre compras a proveedores no obligados a facturar y emita el documento soporte.
            </p>
          </div>
          <Link to="/listados/documentos-soporte" className="text-sm font-semibold text-blue-600 hover:text-blue-700">
            Volver al listado
          </Link>
        </div>
      </div>

      <DocumentoSoporteForm onSubmit={handleSubmit} loading={loading} />
    </div>
  );
}
