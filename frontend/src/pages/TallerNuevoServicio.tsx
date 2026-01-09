import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Search } from 'lucide-react';
import { servicioAPI } from '../api/taller';
import { mecanicoAPI } from '../api/taller';
import { ventasApi } from '../api/ventas';
import { Mecanico, Cliente, ServicioMotoCreate } from '../types';
import { useAuthStore } from '../store/authStore';
import toast from 'react-hot-toast';

export default function TallerNuevoServicio() {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [formData, setFormData] = useState<ServicioMotoCreate>({
    placa: '',
    marca: '',
    modelo: '',
    color: '',
    cliente: 0,
    mecanico: 0,
    recibido_por: user?.id || 0,
    fecha_estimada_entrega: null,
    kilometraje: null,
    nivel_gasolina: '',
    observaciones_ingreso: '',
    diagnostico: '',
    costo_mano_obra: '0'
  });

  const [mecanicos, setMecanicos] = useState<Mecanico[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [busquedaCliente, setBusquedaCliente] = useState('');
  const [clienteSeleccionado, setClienteSeleccionado] = useState<Cliente | null>(null);
  const [loading, setLoading] = useState(false);
  const [mostrarResultadosClientes, setMostrarResultadosClientes] = useState(false);

  useEffect(() => {
    cargarMecanicos();
  }, []);

  const cargarMecanicos = async () => {
    try {
      const response = await mecanicoAPI.getAll();
      setMecanicos(response.results);
    } catch (error) {
      console.error('Error al cargar mecánicos:', error);
      toast.error('Error al cargar mecánicos');
    }
  };

  const buscarClientes = async () => {
    if (!busquedaCliente) {
      setClientes([]);
      return;
    }

    try {
      const response = await ventasApi.buscarCliente(busquedaCliente);
      setClientes([response]);
      setMostrarResultadosClientes(true);
    } catch (error: any) {
      toast.error('Cliente no encontrado');
      setClientes([]);
    }
  };

  const seleccionarCliente = (cliente: Cliente) => {
    setClienteSeleccionado(cliente);
    setFormData({ ...formData, cliente: cliente.id });
    setBusquedaCliente(cliente.nombre);
    setMostrarResultadosClientes(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.placa || !formData.marca || !formData.cliente || !formData.mecanico) {
      toast.error('Por favor completa los campos requeridos');
      return;
    }

    try {
      setLoading(true);
      const servicio = await servicioAPI.create(formData);
      toast.success('Servicio creado exitosamente');
      navigate(`/taller/${servicio.id}`);
    } catch (error: any) {
      console.error('Error al crear servicio:', error);
      toast.error(error.response?.data?.error || 'Error al crear servicio');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    navigate('/taller');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center">
            <button
              onClick={handleCancel}
              className="mr-4 p-2 rounded-md hover:bg-gray-100"
            >
              <ArrowLeft className="h-6 w-6 text-gray-600" />
            </button>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Nuevo Servicio</h1>
              <p className="text-sm text-gray-500 mt-1">
                Ingreso de motocicleta al taller
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Formulario */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Información del Vehículo */}
          <div className="bg-white shadow sm:rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Información del Vehículo
              </h3>
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Placa *
                  </label>
                  <input
                    type="text"
                    value={formData.placa}
                    onChange={(e) =>
                      setFormData({ ...formData, placa: e.target.value.toUpperCase() })
                    }
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Marca *
                  </label>
                  <input
                    type="text"
                    value={formData.marca}
                    onChange={(e) => setFormData({ ...formData, marca: e.target.value })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Modelo
                  </label>
                  <input
                    type="text"
                    value={formData.modelo}
                    onChange={(e) => setFormData({ ...formData, modelo: e.target.value })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Color
                  </label>
                  <input
                    type="text"
                    value={formData.color}
                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Kilometraje
                  </label>
                  <input
                    type="number"
                    value={formData.kilometraje || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        kilometraje: e.target.value ? parseInt(e.target.value) : null
                      })
                    }
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Nivel de Gasolina
                  </label>
                  <select
                    value={formData.nivel_gasolina}
                    onChange={(e) =>
                      setFormData({ ...formData, nivel_gasolina: e.target.value })
                    }
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="">Seleccionar...</option>
                    <option value="Vacío">Vacío</option>
                    <option value="1/4">1/4</option>
                    <option value="1/2">1/2</option>
                    <option value="3/4">3/4</option>
                    <option value="Lleno">Lleno</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Cliente */}
          <div className="bg-white shadow sm:rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Cliente
              </h3>
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <input
                    type="text"
                    placeholder="Buscar por número de documento"
                    value={busquedaCliente}
                    onChange={(e) => setBusquedaCliente(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), buscarClientes())}
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                  {mostrarResultadosClientes && clientes.length > 0 && (
                    <div className="absolute z-10 mt-1 w-full bg-white shadow-lg rounded-md border border-gray-200">
                      {clientes.map((cliente) => (
                        <div
                          key={cliente.id}
                          onClick={() => seleccionarCliente(cliente)}
                          className="px-4 py-3 hover:bg-gray-50 cursor-pointer"
                        >
                          <div className="font-medium">{cliente.nombre}</div>
                          <div className="text-sm text-gray-500">
                            {cliente.tipo_documento}: {cliente.numero_documento}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={buscarClientes}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  <Search className="h-5 w-5" />
                </button>
              </div>
              {clienteSeleccionado && (
                <div className="mt-4 p-4 bg-blue-50 rounded-md">
                  <p className="font-medium">{clienteSeleccionado.nombre}</p>
                  <p className="text-sm text-gray-600">
                    {clienteSeleccionado.telefono} - {clienteSeleccionado.email}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Asignación */}
          <div className="bg-white shadow sm:rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Asignación
              </h3>
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Mecánico Asignado *
                  </label>
                  <select
                    value={formData.mecanico}
                    onChange={(e) =>
                      setFormData({ ...formData, mecanico: parseInt(e.target.value) })
                    }
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  >
                    <option value="">Seleccionar mecánico...</option>
                    {mecanicos.map((mecanico) => (
                      <option key={mecanico.id} value={mecanico.id}>
                        {mecanico.usuario_nombre} - {mecanico.especialidad}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Fecha Estimada de Entrega
                  </label>
                  <input
                    type="datetime-local"
                    value={formData.fecha_estimada_entrega || ''}
                    onChange={(e) =>
                      setFormData({ ...formData, fecha_estimada_entrega: e.target.value || null })
                    }
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Observaciones */}
          <div className="bg-white shadow sm:rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Observaciones y Diagnóstico
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Observaciones al Ingreso *
                  </label>
                  <textarea
                    rows={4}
                    value={formData.observaciones_ingreso}
                    onChange={(e) =>
                      setFormData({ ...formData, observaciones_ingreso: e.target.value })
                    }
                    placeholder="Estado de la moto, daños existentes, accesorios, etc."
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Diagnóstico Inicial
                  </label>
                  <textarea
                    rows={3}
                    value={formData.diagnostico}
                    onChange={(e) => setFormData({ ...formData, diagnostico: e.target.value })}
                    placeholder="Problema reportado por el cliente..."
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Costo Estimado Mano de Obra
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.costo_mano_obra}
                    onChange={(e) =>
                      setFormData({ ...formData, costo_mano_obra: e.target.value })
                    }
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Botones */}
          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={handleCancel}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            >
              <Save className="h-5 w-5 mr-2" />
              {loading ? 'Guardando...' : 'Crear Servicio'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
