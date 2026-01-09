import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Eye, Calendar, User, DollarSign } from 'lucide-react';
import {
  servicioAPI,
  estadoColors,
  formatCurrency,
  formatDate
} from '../api/taller';
import type { ServicioMotoDetalle } from '../types';
import toast from 'react-hot-toast';

export default function TallerHistorial() {
  const { placa } = useParams<{ placa: string }>();
  const navigate = useNavigate();

  const [servicios, setServicios] = useState<ServicioMotoDetalle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (placa) {
      cargarHistorial();
    }
  }, [placa]);

  const cargarHistorial = async () => {
    try {
      setLoading(true);
      const data = await servicioAPI.historialPorPlaca(placa!);
      setServicios(data);
    } catch (error) {
      console.error('Error al cargar historial:', error);
      toast.error('Error al cargar historial');
    } finally {
      setLoading(false);
    }
  };

  const verDetalle = (id: number) => {
    navigate(`/taller/${id}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center">
            <button
              onClick={() => navigate(-1)}
              className="mr-4 p-2 rounded-md hover:bg-gray-100"
            >
              <ArrowLeft className="h-6 w-6 text-gray-600" />
            </button>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Historial de Servicios
              </h1>
              <p className="text-sm text-gray-500 mt-1">Placa: {placa}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Contenido */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : servicios.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <Calendar className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">
              No hay historial
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              No se encontraron servicios previos para esta placa.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {servicios.map((servicio) => (
              <div
                key={servicio.id}
                className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow"
              >
                <div className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center">
                        <h3 className="text-lg font-semibold text-gray-900">
                          {servicio.numero_servicio}
                        </h3>
                        <span
                          className={`ml-3 px-3 py-1 text-xs font-semibold rounded-full ${
                            estadoColors[servicio.estado]
                          }`}
                        >
                          {servicio.estado_display}
                        </span>
                      </div>

                      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="flex items-start">
                          <Calendar className="h-5 w-5 text-gray-400 mr-2 mt-0.5" />
                          <div>
                            <p className="text-xs text-gray-500">Fecha de Ingreso</p>
                            <p className="text-sm font-medium text-gray-900">
                              {formatDate(servicio.fecha_ingreso)}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-start">
                          <User className="h-5 w-5 text-gray-400 mr-2 mt-0.5" />
                          <div>
                            <p className="text-xs text-gray-500">Cliente</p>
                            <p className="text-sm font-medium text-gray-900">
                              {servicio.cliente_info.nombre}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-start">
                          <DollarSign className="h-5 w-5 text-gray-400 mr-2 mt-0.5" />
                          <div>
                            <p className="text-xs text-gray-500">Total</p>
                            <p className="text-sm font-medium text-gray-900">
                              {formatCurrency(servicio.total)}
                            </p>
                          </div>
                        </div>
                      </div>

                      {servicio.diagnostico && (
                        <div className="mt-4">
                          <p className="text-xs text-gray-500">Diagnóstico</p>
                          <p className="text-sm text-gray-900 mt-1">
                            {servicio.diagnostico}
                          </p>
                        </div>
                      )}

                      {servicio.trabajo_realizado && (
                        <div className="mt-4">
                          <p className="text-xs text-gray-500">Trabajo Realizado</p>
                          <p className="text-sm text-gray-900 mt-1 whitespace-pre-line">
                            {servicio.trabajo_realizado}
                          </p>
                        </div>
                      )}

                      {servicio.consumos_repuestos.length > 0 && (
                        <div className="mt-4">
                          <p className="text-xs text-gray-500 mb-2">
                            Repuestos Utilizados
                          </p>
                          <div className="bg-gray-50 rounded-md p-3">
                            <ul className="space-y-1">
                              {servicio.consumos_repuestos.map((consumo) => (
                                <li
                                  key={consumo.id}
                                  className="text-sm text-gray-700 flex justify-between"
                                >
                                  <span>
                                    {consumo.producto_codigo} - {consumo.producto_nombre} x
                                    {consumo.cantidad}
                                  </span>
                                  <span className="font-medium">
                                    {formatCurrency(consumo.subtotal)}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => verDetalle(servicio.id)}
                      className="ml-4 inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      Ver Detalle
                    </button>
                  </div>
                </div>
              </div>
            ))}

            {/* Resumen */}
            <div className="bg-blue-50 rounded-lg p-6 mt-8">
              <h3 className="text-lg font-medium text-blue-900 mb-4">
                Resumen del Historial
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-blue-700">Total de Servicios</p>
                  <p className="text-2xl font-bold text-blue-900">
                    {servicios.length}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-blue-700">Servicios Completados</p>
                  <p className="text-2xl font-bold text-blue-900">
                    {servicios.filter((s) => s.estado === 'ENTREGADO').length}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-blue-700">Inversión Total</p>
                  <p className="text-2xl font-bold text-blue-900">
                    {formatCurrency(
                      servicios.reduce((sum, s) => sum + parseFloat(s.total), 0)
                    )}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
