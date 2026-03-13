import { useState } from 'react';
import type { CrearDocumentoSoportePayload } from '../services/documentosSoporteApi';

interface DocumentoSoporteFormProps {
  loading: boolean;
  onSubmit: (payload: CrearDocumentoSoportePayload) => Promise<void>;
}

export default function DocumentoSoporteForm({ onSubmit, loading }: DocumentoSoporteFormProps) {
  const [proveedorNombre, setProveedorNombre] = useState('');
  const [proveedorDocumento, setProveedorDocumento] = useState('');
  const [tipoDocumentoProveedor, setTipoDocumentoProveedor] = useState('CC');
  const [descripcion, setDescripcion] = useState('');
  const [cantidad, setCantidad] = useState('1');
  const [valorUnitario, setValorUnitario] = useState('');
  const [metodoPago, setMetodoPago] = useState('CONTADO');

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit({
      proveedor_nombre: proveedorNombre.trim(),
      proveedor_documento: proveedorDocumento.trim(),
      tipo_documento_proveedor: tipoDocumentoProveedor,
      descripcion: descripcion.trim(),
      cantidad: Number(cantidad),
      valor_unitario: Number(valorUnitario),
      metodo_pago: metodoPago,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg bg-white p-6 shadow">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Proveedor nombre
          <input
            value={proveedorNombre}
            onChange={(event) => setProveedorNombre(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Proveedor documento
          <input
            value={proveedorDocumento}
            onChange={(event) => setProveedorDocumento(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Tipo documento proveedor
          <select
            value={tipoDocumentoProveedor}
            onChange={(event) => setTipoDocumentoProveedor(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          >
            <option value="CC">CC</option>
            <option value="CE">CE</option>
            <option value="NIT">NIT</option>
            <option value="PASAPORTE">Pasaporte</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Método de pago
          <select
            value={metodoPago}
            onChange={(event) => setMetodoPago(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          >
            <option value="CONTADO">Contado</option>
            <option value="CREDITO">Crédito</option>
            <option value="TRANSFERENCIA">Transferencia</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Descripción
          <textarea
            value={descripcion}
            onChange={(event) => setDescripcion(event.target.value)}
            className="min-h-24 rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Cantidad
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={cantidad}
            onChange={(event) => setCantidad(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Valor unitario
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorUnitario}
            onChange={(event) => setValorUnitario(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
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
          {loading ? 'Emitiendo...' : 'Emitir documento soporte'}
        </button>
      </div>
    </form>
  );
}
