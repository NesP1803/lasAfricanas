import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNotification } from '../../../contexts/NotificationContext';
import DocumentoSoporteForm from '../components/DocumentoSoporteForm';
import { documentosSoporteApi, type CrearDocumentoSoportePayload } from '../services/documentosSoporteApi';
import { configuracionAPI, type FacturacionRango } from '../../../api/configuracion';

export default function CrearDocumentoSoportePage() {
  const [loading, setLoading] = useState(false);
  const [rangoDocumentoSoporteActivo, setRangoDocumentoSoporteActivo] = useState<FacturacionRango | null>(null);
  const navigate = useNavigate();
  const { showNotification } = useNotification();

  useEffect(() => {
    configuracionAPI
      .listarRangosFacturacion({ document_code: 'DOCUMENTO_SOPORTE' })
      .then((rangos) => {
        const seleccionado = rangos.find((rango) => rango.is_selected_local);
        const asociado = rangos.find((rango) => rango.is_associated_to_software);
        setRangoDocumentoSoporteActivo(seleccionado ?? asociado ?? rangos[0] ?? null);
      })
      .catch(() => setRangoDocumentoSoporteActivo(null));
  }, []);

  const handleSubmit = async (payload: CrearDocumentoSoportePayload) => {
    setLoading(true);
    try {
      const response = await documentosSoporteApi.crearDocumentoSoporte(payload);
      if (response?.result === 'PENDING_DIAN_CONFLICT') {
        showNotification({
          message:
            response.warning ||
            response.detail ||
            'Hay un documento soporte pendiente en DIAN. Sincronice y reintente.',
          type: 'info',
        });
        navigate('/listados/documentos-soporte');
        return;
      }
      showNotification({
        message: 'Documento soporte emitido correctamente.',
        type: 'success',
      });
      navigate('/listados/documentos-soporte');
    } catch (error) {
      const detail =
        axios.isAxiosError<{ detail?: string }>(error)
          ? error.response?.data?.detail
          : undefined;
      showNotification({
        message: detail || 'No fue posible emitir el documento soporte.',
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

        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Generar documento soporte
          </p>
          <p className="text-sm font-medium text-slate-800">
            {rangoDocumentoSoporteActivo
              ? `${rangoDocumentoSoporteActivo.prefijo}-${rangoDocumentoSoporteActivo.consecutivo_actual}`
              : 'Sin rango seleccionado'}
          </p>
        </div>
      </div>

      <DocumentoSoporteForm onSubmit={handleSubmit} loading={loading} />
    </div>
  );
}
