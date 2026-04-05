import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useNotification } from '../../../contexts/NotificationContext';
import DocumentosSoporteTable from '../components/DocumentosSoporteTable';
import { documentosSoporteApi, type DocumentoSoporte } from '../services/documentosSoporteApi';

export default function DocumentosSoportePage() {
  const [documentos, setDocumentos] = useState<DocumentoSoporte[]>([]);
  const [loading, setLoading] = useState(false);
  const { showNotification } = useNotification();

  const cargarDocumentos = useCallback(async () => {
    setLoading(true);
    try {
      const data = await documentosSoporteApi.getDocumentosSoporte();
      setDocumentos(data);
    } catch {
      setDocumentos([]);
      showNotification({
        message: 'No fue posible cargar los documentos soporte.',
        type: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [showNotification]);

  useEffect(() => {
    cargarDocumentos();
  }, [cargarDocumentos]);

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="flex flex-col gap-3 rounded-lg bg-white p-4 shadow sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Documentos Soporte</h2>
          <p className="text-sm text-slate-500">
            Consulte documentos soporte emitidos y descargue archivos XML o PDF.
          </p>
        </div>
        <Link
          to="/facturacion/documento-soporte"
          className="inline-flex w-fit rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Crear documento soporte
        </Link>
      </div>

      <DocumentosSoporteTable documentos={documentos} loading={loading} onRefresh={cargarDocumentos} />
    </div>
  );
}
