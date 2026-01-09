import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Edit,
  Save,
  Plus,
  Trash2,
  FileText,
  History,
  DollarSign,
  Package,
  Clock,
  User,
  Phone,
  Mail,
  MapPin
} from 'lucide-react';
import {
  servicioAPI,
  estadoColors,
  estadoNames,
  formatCurrency,
  formatDate,
  puedeTransicionar
} from '../api/taller';
import { ServicioMotoDetalle, EstadoServicio, ConsumoRepuesto, Producto } from '../types';
import { productosApi } from '../api/productos';
import toast from 'react-hot-toast';

export default function TallerDetalle() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [servicio, setServicio] = useState<ServicioMotoDetalle | null>(null);
  const [loading, setLoading] = useState(true);
  const [editando, setEditando] = useState(false);

  // Modal de cambio de estado
  const [mostrarCambioEstado, setMostrarCambioEstado] = useState(false);
  const [nuevoEstado, setNuevoEstado] = useState<EstadoServicio | ''>('');
  const [observacionesEstado, setObservacionesEstado] = useState('');

  // Modal de agregar repuesto
  const [mostrarAgregarRepuesto, setMostrarAgregarRepuesto] = useState(false);
  const [busquedaProducto, setBusquedaProducto] = useState('');
  const [productosEncontrados, setProductosEncontrados] = useState<Producto[]>([]);
  const [productoSeleccionado, setProductoSeleccionado] = useState<Producto | null>(null);
  const [cantidadRepuesto, setCantidadRepuesto] = useState(1);
  const [precioRepuesto, setPrecioRepuesto] = useState('');
  const [descuentoRepuesto, setDescuentoRepuesto] = useState('0');

  // Estados editables
  const [diagnostico, setDiagnostico] = useState('');
  const [trabajoRealizado, setTrabajoRealizado] = useState('');
  const [recomendaciones, setRecomendaciones] = useState('');
  const [costoManoObra, setCostoManoObra] = useState('');

  useEffect(() => {
    if (id) {
      cargarServicio();
    }
  }, [id]);

  useEffect(() => {
    if (servicio) {
      setDiagnostico(servicio.diagnostico);
      setTrabajoRealizado(servicio.trabajo_realizado);
      setRecomendaciones(servicio.recomendaciones);
      setCostoManoObra(servicio.costo_mano_obra);
    }
  }, [servicio]);

  const cargarServicio = async () => {
    try {
      setLoading(true);
      const data = await servicioAPI.getById(parseInt(id!));
      setServicio(data);
    } catch (error) {
      console.error('Error al cargar servicio:', error);
      toast.error('Error al cargar servicio');
      navigate('/taller');
    } finally {
      setLoading(false);
    }
  };

  const handleCambiarEstado = async () => {
    if (!nuevoEstado || !servicio) return;

    if (!puedeTransicionar(servicio.estado, nuevoEstado)) {
      toast.error('Transición de estado no permitida');
      return;
    }

    try {
      await servicioAPI.cambiarEstado(servicio.id, nuevoEstado, observacionesEstado);
      toast.success('Estado actualizado exitosamente');
      setMostrarCambioEstado(false);
      setNuevoEstado('');
      setObservacionesEstado('');
      cargarServicio();
    } catch (error: any) {
      console.error('Error al cambiar estado:', error);
      toast.error(error.response?.data?.error || 'Error al cambiar estado');
    }
  };

  const buscarProductos = async () => {
    if (!busquedaProducto) return;

    try {
      const productos = await productosApi.buscarPorCodigo(busquedaProducto);
      setProductosEncontrados([productos]);
    } catch (error) {
      toast.error('Producto no encontrado');
      setProductosEncontrados([]);
    }
  };

  const seleccionarProducto = (producto: Producto) => {
    setProductoSeleccionado(producto);
    setPrecioRepuesto(producto.precio_venta);
    setBusquedaProducto(producto.nombre);
    setProductosEncontrados([]);
  };

  const handleAgregarRepuesto = async () => {
    if (!servicio || !productoSeleccionado) return;

    try {
      await servicioAPI.agregarRepuesto(servicio.id, {
        producto_id: productoSeleccionado.id,
        cantidad: cantidadRepuesto,
        precio_unitario: precioRepuesto,
        descuento: descuentoRepuesto
      });

      toast.success('Repuesto agregado exitosamente');
      setMostrarAgregarRepuesto(false);
      setBusquedaProducto('');
      setProductoSeleccionado(null);
      setCantidadRepuesto(1);
      setPrecioRepuesto('');
      setDescuentoRepuesto('0');
      cargarServicio();
    } catch (error: any) {
      console.error('Error al agregar repuesto:', error);
      toast.error(error.response?.data?.error || 'Error al agregar repuesto');
    }
  };

  const handleGuardarCambios = async () => {
    if (!servicio) return;

    try {
      await servicioAPI.update(servicio.id, {
        diagnostico,
        trabajo_realizado: trabajoRealizado,
        recomendaciones,
        costo_mano_obra: costoManoObra
      });

      toast.success('Cambios guardados exitosamente');
      setEditando(false);
      cargarServicio();
    } catch (error: any) {
      console.error('Error al guardar cambios:', error);
      toast.error('Error al guardar cambios');
    }
  };

  const handleFacturar = async () => {
    if (!servicio) return;

    if (servicio.estado !== 'TERMINADO' && servicio.estado !== 'ENTREGADO') {
      toast.error('El servicio debe estar terminado para facturar');
      return;
    }

    try {
      await servicioAPI.facturar(servicio.id, {
        tipo_comprobante: 'FACTURA',
        medio_pago: 'EFECTIVO',
        efectivo_recibido: servicio.total
      });

      toast.success('Servicio facturado exitosamente');
      cargarServicio();
    } catch (error: any) {
      console.error('Error al facturar:', error);
      toast.error(error.response?.data?.error || 'Error al facturar');
    }
  };

  const verHistorialPlaca = () => {
    if (servicio) {
      navigate(`/taller/historial/${servicio.placa}`);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!servicio) {
    return null;
  }

  const estadosPermitidos = servicio.estado === 'INGRESADO'
    ? ['EN_DIAGNOSTICO', 'CANCELADO']
    : servicio.estado === 'EN_DIAGNOSTICO'
    ? ['COTIZADO', 'CANCELADO']
    : servicio.estado === 'COTIZADO'
    ? ['APROBADO', 'CANCELADO']
    : servicio.estado === 'APROBADO'
    ? ['EN_REPARACION', 'CANCELADO']
    : servicio.estado === 'EN_REPARACION'
    ? ['TERMINADO', 'CANCELADO']
    : servicio.estado === 'TERMINADO'
    ? ['ENTREGADO', 'EN_REPARACION']
    : [];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => navigate('/taller')}
                className="mr-4 p-2 rounded-md hover:bg-gray-100"
              >
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </button>
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  {servicio.numero_servicio}
                </h1>
                <p className="text-sm text-gray-500 mt-1">
                  {servicio.placa} - {servicio.marca} {servicio.modelo}
                </p>
              </div>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={verHistorialPlaca}
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <History className="h-5 w-5 mr-2" />
                Historial
              </button>
              {!servicio.venta && (servicio.estado === 'TERMINADO' || servicio.estado === 'ENTREGADO') && (
                <button
                  onClick={handleFacturar}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
                >
                  <DollarSign className="h-5 w-5 mr-2" />
                  Facturar
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Columna Principal */}
          <div className="lg:col-span-2 space-y-6">
            {/* Estado y Acciones */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Estado del Servicio</h3>
                  <span
                    className={`mt-2 inline-flex px-3 py-1 text-sm font-semibold rounded-full ${
                      estadoColors[servicio.estado]
                    }`}
                  >
                    {servicio.estado_display}
                  </span>
                </div>
                {estadosPermitidos.length > 0 && (
                  <button
                    onClick={() => setMostrarCambioEstado(true)}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
                  >
                    Cambiar Estado
                  </button>
                )}
              </div>
            </div>

            {/* Información del Servicio */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  Información del Servicio
                </h3>
                {!editando ? (
                  <button
                    onClick={() => setEditando(true)}
                    className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
                  >
                    <Edit className="h-4 w-4 mr-1" />
                    Editar
                  </button>
                ) : (
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setEditando(false)}
                      className="text-sm text-gray-600 hover:text-gray-800"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={handleGuardarCambios}
                      className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800"
                    >
                      <Save className="h-4 w-4 mr-1" />
                      Guardar
                    </button>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Diagnóstico
                  </label>
                  {editando ? (
                    <textarea
                      rows={3}
                      value={diagnostico}
                      onChange={(e) => setDiagnostico(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  ) : (
                    <p className="mt-1 text-sm text-gray-900">
                      {servicio.diagnostico || 'Sin diagnóstico'}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Trabajo Realizado
                  </label>
                  {editando ? (
                    <textarea
                      rows={4}
                      value={trabajoRealizado}
                      onChange={(e) => setTrabajoRealizado(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  ) : (
                    <p className="mt-1 text-sm text-gray-900 whitespace-pre-line">
                      {servicio.trabajo_realizado || 'Sin registro'}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Recomendaciones
                  </label>
                  {editando ? (
                    <textarea
                      rows={3}
                      value={recomendaciones}
                      onChange={(e) => setRecomendaciones(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  ) : (
                    <p className="mt-1 text-sm text-gray-900">
                      {servicio.recomendaciones || 'Sin recomendaciones'}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Costo Mano de Obra
                  </label>
                  {editando ? (
                    <input
                      type="number"
                      step="0.01"
                      value={costoManoObra}
                      onChange={(e) => setCostoManoObra(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  ) : (
                    <p className="mt-1 text-sm text-gray-900">
                      {formatCurrency(servicio.costo_mano_obra)}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Repuestos Consumidos */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">
                  Repuestos Consumidos
                </h3>
                {servicio.estado !== 'ENTREGADO' && servicio.estado !== 'CANCELADO' && (
                  <button
                    onClick={() => setMostrarAgregarRepuesto(true)}
                    className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Agregar
                  </button>
                )}
              </div>

              {servicio.consumos_repuestos.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">
                  No se han registrado repuestos
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Código
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Producto
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                          Cantidad
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                          Precio
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                          Subtotal
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {servicio.consumos_repuestos.map((consumo) => (
                        <tr key={consumo.id}>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            {consumo.producto_codigo}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            {consumo.producto_nombre}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-gray-900">
                            {consumo.cantidad}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-gray-900">
                            {formatCurrency(consumo.precio_unitario)}
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">
                            {formatCurrency(consumo.subtotal)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-gray-50">
                      <tr>
                        <td colSpan={4} className="px-4 py-3 text-sm font-medium text-right text-gray-900">
                          Total Repuestos:
                        </td>
                        <td className="px-4 py-3 text-sm font-bold text-right text-gray-900">
                          {formatCurrency(servicio.costo_repuestos)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Columna Lateral */}
          <div className="space-y-6">
            {/* Resumen de Costos */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Resumen de Costos
              </h3>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Mano de Obra:</span>
                  <span className="font-medium text-gray-900">
                    {formatCurrency(servicio.costo_mano_obra)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Repuestos:</span>
                  <span className="font-medium text-gray-900">
                    {formatCurrency(servicio.costo_repuestos)}
                  </span>
                </div>
                {parseFloat(servicio.descuento) > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Descuento:</span>
                    <span className="font-medium text-red-600">
                      -{formatCurrency(servicio.descuento)}
                    </span>
                  </div>
                )}
                <div className="pt-3 border-t border-gray-200">
                  <div className="flex justify-between">
                    <span className="text-base font-medium text-gray-900">Total:</span>
                    <span className="text-xl font-bold text-blue-600">
                      {formatCurrency(servicio.total)}
                    </span>
                  </div>
                </div>
                {servicio.venta && (
                  <div className="pt-3 border-t border-gray-200">
                    <div className="flex items-center text-sm text-green-600">
                      <FileText className="h-4 w-4 mr-1" />
                      Facturado
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Información del Cliente */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Cliente</h3>
              <div className="space-y-3">
                <div className="flex items-start">
                  <User className="h-5 w-5 text-gray-400 mr-2 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {servicio.cliente_info.nombre}
                    </p>
                    <p className="text-xs text-gray-500">
                      {servicio.cliente_info.tipo_documento}: {servicio.cliente_info.numero_documento}
                    </p>
                  </div>
                </div>
                {servicio.cliente_info.telefono && (
                  <div className="flex items-center">
                    <Phone className="h-5 w-5 text-gray-400 mr-2" />
                    <p className="text-sm text-gray-900">
                      {servicio.cliente_info.telefono}
                    </p>
                  </div>
                )}
                {servicio.cliente_info.email && (
                  <div className="flex items-center">
                    <Mail className="h-5 w-5 text-gray-400 mr-2" />
                    <p className="text-sm text-gray-900">
                      {servicio.cliente_info.email}
                    </p>
                  </div>
                )}
                {servicio.cliente_info.direccion && (
                  <div className="flex items-start">
                    <MapPin className="h-5 w-5 text-gray-400 mr-2 mt-0.5" />
                    <p className="text-sm text-gray-900">
                      {servicio.cliente_info.direccion}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Información del Mecánico */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Mecánico</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {servicio.mecanico_info.usuario_nombre}
                  </p>
                  <p className="text-xs text-gray-500">
                    {servicio.mecanico_info.especialidad}
                  </p>
                </div>
              </div>
            </div>

            {/* Fechas */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Fechas</h3>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-gray-500">Ingreso</p>
                  <p className="text-sm font-medium text-gray-900">
                    {formatDate(servicio.fecha_ingreso)}
                  </p>
                </div>
                {servicio.fecha_estimada_entrega && (
                  <div>
                    <p className="text-xs text-gray-500">Entrega Estimada</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(servicio.fecha_estimada_entrega)}
                    </p>
                  </div>
                )}
                {servicio.fecha_entrega_real && (
                  <div>
                    <p className="text-xs text-gray-500">Entrega Real</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(servicio.fecha_entrega_real)}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Detalles del Vehículo */}
            <div className="bg-white shadow sm:rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Detalles del Vehículo
              </h3>
              <div className="space-y-2 text-sm">
                {servicio.kilometraje && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Kilometraje:</span>
                    <span className="text-gray-900">{servicio.kilometraje.toLocaleString()} km</span>
                  </div>
                )}
                {servicio.nivel_gasolina && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Gasolina:</span>
                    <span className="text-gray-900">{servicio.nivel_gasolina}</span>
                  </div>
                )}
                {servicio.color && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Color:</span>
                    <span className="text-gray-900">{servicio.color}</span>
                  </div>
                )}
                <div className="pt-3 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-1">Observaciones al Ingreso:</p>
                  <p className="text-sm text-gray-900 whitespace-pre-line">
                    {servicio.observaciones_ingreso}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal Cambiar Estado */}
      {mostrarCambioEstado && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Cambiar Estado del Servicio
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Nuevo Estado
                </label>
                <select
                  value={nuevoEstado}
                  onChange={(e) => setNuevoEstado(e.target.value as EstadoServicio)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Seleccionar estado...</option>
                  {estadosPermitidos.map((estado) => (
                    <option key={estado} value={estado}>
                      {estadoNames[estado as EstadoServicio]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Observaciones
                </label>
                <textarea
                  rows={3}
                  value={observacionesEstado}
                  onChange={(e) => setObservacionesEstado(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Notas sobre el cambio de estado..."
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setMostrarCambioEstado(false);
                  setNuevoEstado('');
                  setObservacionesEstado('');
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleCambiarEstado}
                disabled={!nuevoEstado}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
              >
                Cambiar Estado
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Agregar Repuesto */}
      {mostrarAgregarRepuesto && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Agregar Repuesto
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Buscar Producto
                </label>
                <div className="flex mt-1">
                  <input
                    type="text"
                    value={busquedaProducto}
                    onChange={(e) => setBusquedaProducto(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && buscarProductos()}
                    placeholder="Código del producto"
                    className="flex-1 border border-gray-300 rounded-l-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                  <button
                    onClick={buscarProductos}
                    className="px-4 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700"
                  >
                    <Package className="h-5 w-5" />
                  </button>
                </div>
                {productosEncontrados.length > 0 && (
                  <div className="mt-2 border border-gray-200 rounded-md">
                    {productosEncontrados.map((producto) => (
                      <div
                        key={producto.id}
                        onClick={() => seleccionarProducto(producto)}
                        className="px-4 py-3 hover:bg-gray-50 cursor-pointer"
                      >
                        <div className="font-medium">{producto.nombre}</div>
                        <div className="text-sm text-gray-500">
                          {producto.codigo} - Stock: {producto.stock}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {productoSeleccionado && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Cantidad
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={cantidadRepuesto}
                      onChange={(e) => setCantidadRepuesto(parseInt(e.target.value))}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Precio Unitario
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={precioRepuesto}
                      onChange={(e) => setPrecioRepuesto(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Descuento
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={descuentoRepuesto}
                      onChange={(e) => setDescuentoRepuesto(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </>
              )}
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setMostrarAgregarRepuesto(false);
                  setBusquedaProducto('');
                  setProductoSeleccionado(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleAgregarRepuesto}
                disabled={!productoSeleccionado}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
              >
                Agregar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
