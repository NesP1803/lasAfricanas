import { useEffect, useState } from 'react';
import FacturasTable from '../components/FacturasTable';
import { facturacionApi, type FacturaElectronica } from '../services/facturacionApi';
import { useNotification } from '../../../contexts/NotificationContext';

export default function FacturasElectronicasPage() {
  const [facturas, setFacturas] = useState<FacturaElectronica[]>([]);
  const [loading, setLoading] = useState(false);
  const { showNotification } = useNotification();

  useEffect(() => {
    const cargarFacturas = async () => {
      setLoading(true);
      try {
        const data = await facturacionApi.getFacturas();
        setFacturas(data);
      } catch {
        setFacturas([]);
        showNotification({
          message: 'No fue posible cargar las facturas electrónicas.',
          type: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    cargarFacturas();
  }, [showNotification]);

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="rounded-lg bg-white p-4 shadow">
        <h2 className="text-xl font-semibold text-slate-800">Facturación Electrónica</h2>
        <p className="text-sm text-slate-500">
          Consulte el estado DIAN y realice acciones de XML, PDF y correo para cada factura.
        </p>
      </div>

      <FacturasTable facturas={facturas} loading={loading} />
    </div>
  );
}
