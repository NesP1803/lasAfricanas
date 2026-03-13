import { useState } from 'react';
import type { CrearNotaCreditoPayload } from '../services/notasCreditoApi';

interface NotaCreditoFormProps {
  onSubmit: (data: CrearNotaCreditoPayload) => Promise<void>;
  loading: boolean;
}

export default function NotaCreditoForm({ onSubmit, loading }: NotaCreditoFormProps) {
  const [facturaAsociada, setFacturaAsociada] = useState('');
  const [motivo, setMotivo] = useState('');
  const [itemsAjustar, setItemsAjustar] = useState('');
  const [valorAjuste, setValorAjuste] = useState('');

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit({
      factura_asociada: facturaAsociada.trim(),
      motivo: motivo.trim(),
      items_ajustar: itemsAjustar.trim(),
      valor_ajuste: Number(valorAjuste),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg bg-white p-6 shadow">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Factura asociada
          <input
            value={facturaAsociada}
            onChange={(event) => setFacturaAsociada(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Valor ajuste
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorAjuste}
            onChange={(event) => setValorAjuste(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Motivo
          <textarea
            value={motivo}
            onChange={(event) => setMotivo(event.target.value)}
            className="min-h-24 rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Items a ajustar
          <textarea
            value={itemsAjustar}
            onChange={(event) => setItemsAjustar(event.target.value)}
            className="min-h-24 rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>
      </div>

      <div className="mt-5 flex justify-end">
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-70"
          disabled={loading}
        >
          {loading ? 'Emitiendo...' : 'Emitir nota crédito'}
        </button>
      </div>
    </form>
  );
}
