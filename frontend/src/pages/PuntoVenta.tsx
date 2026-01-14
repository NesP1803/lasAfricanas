import { useState } from 'react';
import { ventasApi } from '../api/ventas';
import { useAuth } from '../contexts/AuthContext';
import type { Cliente } from "../api/ventas";

export default function PuntoVenta() {
  const { user } = useAuth();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [buscarCliente, setBuscarCliente] = useState('');

  // Buscar cliente
  const buscarClientePorDocumento = async () => {
    if (!buscarCliente.trim()) return;

    try {
      const clienteEncontrado = await ventasApi.buscarCliente(buscarCliente.trim());
      setCliente(clienteEncontrado);
    } catch (error) {
      alert('Cliente no encontrado');
    }
  };

  return (
    <div className="h-full flex flex-col bg-yellow-50">
      {/* Header */}
      <div className="bg-blue-600 text-white p-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <label className="text-xs font-semibold block mb-1">DIGITE Nº/CC DEL CLIENTE</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Número de documento"
                value={buscarCliente}
                onChange={(e) => setBuscarCliente(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && buscarClientePorDocumento()}
                className="px-3 py-2 rounded text-gray-900 w-48"
              />
              <button
                onClick={buscarClientePorDocumento}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded font-bold"
              >
                ✓
              </button>
            </div>
          </div>

          {cliente && (
            <div className="bg-white text-gray-900 px-4 py-2 rounded">
              <p className="font-bold text-lg">{cliente.nombre}</p>
              <p className="text-sm">{cliente.numero_documento}</p>
            </div>
          )}
        </div>

        <div className="text-right">
          <p className="text-xs">VENDEDOR</p>
          <p className="font-bold text-lg">{user?.username.toUpperCase()}</p>
        </div>
      </div>

    </div>
  );
}
