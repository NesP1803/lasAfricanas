import { useState } from 'react';
import type { CrearNotaCreditoPayload } from '../services/notasCreditoApi';

interface NotaCreditoFormProps {
  onSubmit: (data: CrearNotaCreditoPayload) => Promise<void>;
  loading: boolean;
}

export default function NotaCreditoForm({ onSubmit, loading }: NotaCreditoFormProps) {
  const [motivo, setMotivo] = useState('');
  const [detalleVentaOriginalId, setDetalleVentaOriginalId] = useState('');
  const [cantidad, setCantidad] = useState('1');

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit({
      motivo: motivo.trim(),
      lines: [
        {
          detalle_venta_original_id: Number(detalleVentaOriginalId),
          cantidad_a_acreditar: Number(cantidad),
          afecta_inventario: true,
        },
      ],
    });
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg bg-white p-6 shadow">
      <p className="mb-3 text-sm text-slate-600">Componente legado (mantenido por compatibilidad).</p>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          ID detalle venta
          <input type="number" min="1" value={detalleVentaOriginalId} onChange={(event) => setDetalleVentaOriginalId(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2" required />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Cantidad
          <input type="number" min="0.01" step="0.01" value={cantidad} onChange={(event) => setCantidad(event.target.value)} className="rounded-md border border-slate-300 px-3 py-2" required />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Motivo
          <textarea value={motivo} onChange={(event) => setMotivo(event.target.value)} className="min-h-24 rounded-md border border-slate-300 px-3 py-2" required />
        </label>
      </div>
      <div className="mt-5 flex justify-end">
        <button type="submit" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white" disabled={loading}>
          {loading ? 'Emitiendo...' : 'Emitir nota crédito'}
        </button>
      </div>
    </form>
  );
}
