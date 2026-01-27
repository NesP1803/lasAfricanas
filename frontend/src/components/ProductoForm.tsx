import { useState, useEffect, useMemo } from 'react';
import { X, Plus } from 'lucide-react';
import { inventarioApi } from '../api/inventario';
import { configuracionAPI } from '../api/configuracion';
import type { Producto, Categoria, Proveedor} from "../api/inventario";
import type { Impuesto } from '../types';
import { useNotification } from '../contexts/NotificationContext';


interface ProductoFormProps {
  producto?: Producto | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ProductoForm({ producto, onClose, onSuccess }: ProductoFormProps) {
  const { showNotification } = useNotification();
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [impuestos, setImpuestos] = useState<Impuesto[]>([]);
  const [impuestoSeleccionado, setImpuestoSeleccionado] = useState('');
  const [mostrarCategoriaRapida, setMostrarCategoriaRapida] = useState(false);
  const [nuevaCategoria, setNuevaCategoria] = useState('');
  const [creandoCategoria, setCreandoCategoria] = useState(false);
  const [mostrarProveedorRapido, setMostrarProveedorRapido] = useState(false);
  const [nuevoProveedor, setNuevoProveedor] = useState('');
  const [creandoProveedor, setCreandoProveedor] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<any>({});

  const normalizeIva = (value: string | number) => {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
      return '0.00';
    }
    return numericValue.toFixed(2);
  };

  const [formData, setFormData] = useState({
    codigo: '',
    nombre: '',
    descripcion: '',
    categoria: '',
    proveedor: '',
    precio_venta: '',
    precio_venta_minimo: '',
    stock: '0',
    stock_minimo: '5',
    unidad_medida: 'UND',
    aplica_descuento: true,
    es_servicio: false,
    is_active: true,
  });

  useEffect(() => {
    loadCategorias();
    loadProveedores();
    loadImpuestos();

    if (producto) {
      setFormData({
        codigo: producto.codigo,
        nombre: producto.nombre,
        descripcion: producto.descripcion || '',
        categoria: producto.categoria.toString(),
        proveedor: producto.proveedor ? producto.proveedor.toString() : '',
        precio_venta: producto.precio_venta,
        precio_venta_minimo: producto.precio_venta_minimo,
        stock: producto.stock.toString(),
        stock_minimo: producto.stock_minimo.toString(),
        unidad_medida: producto.unidad_medida,
        aplica_descuento: producto.aplica_descuento,
        es_servicio: producto.es_servicio,
        is_active: producto.is_active,
      });
    }
  }, [producto]);

  const formatPorcentaje = (porcentaje: string) => {
    const numeric = Number(porcentaje);
    if (!Number.isFinite(numeric)) {
      return porcentaje;
    }
    if (Number.isInteger(numeric)) {
      return numeric.toString();
    }
    return numeric.toString();
  };

  const formatImpuestoLabel = (nombre: string, porcentaje: string) => {
    const raw = nombre?.trim() ?? '';
    const lower = raw.toLowerCase();
    const porcentajeLabel = formatPorcentaje(porcentaje);
    if (!raw) {
      return `IVA ${porcentajeLabel}%`;
    }
    if (lower === 'e' || lower.includes('exento') || lower.includes('excento')) {
      return 'Exento';
    }
    if (/^\d+(\.\d+)?%?$/.test(raw)) {
      return `IVA ${porcentajeLabel}%`;
    }
    if (raw.length <= 3 && !lower.includes('iva')) {
      return `IVA ${porcentajeLabel}%`;
    }
    if (lower === 'iva') {
      return `IVA ${porcentajeLabel}%`;
    }
    if (lower.startsWith('iva')) {
      return `IVA ${porcentajeLabel}%`;
    }
    return raw;
  };

  const impuestoOpciones = useMemo(() => {
    const unique = new Map<string, (typeof impuestos)[number] & {
      porcentaje: string;
      label: string;
    }>();
    impuestos.forEach((impuesto) => {
      const match = impuesto.nombre.match(/(\d+(?:\.\d+)?)/);
      const porcentaje = normalizeIva(match ? match[1] : '0');
      const esExento = impuesto.nombre.toLowerCase().includes('exento');
      const porcentajeFinal = esExento ? '0.00' : porcentaje;
      const label = formatImpuestoLabel(impuesto.nombre, porcentajeFinal);
      const key = label.toLowerCase();
      if (!unique.has(key)) {
        unique.set(key, {
          ...impuesto,
          porcentaje: porcentajeFinal,
          label,
        });
      }
    });
    return Array.from(unique.values()).sort((a, b) => {
      const aExento = a.label.toLowerCase() === 'exento';
      const bExento = b.label.toLowerCase() === 'exento';
      if (aExento && !bExento) return 1;
      if (bExento && !aExento) return -1;
      return Number(a.porcentaje) - Number(b.porcentaje);
    });
  }, [impuestos]);

  const loadCategorias = async () => {
    try {
      const data = await inventarioApi.getCategorias({ is_active: true });
      setCategorias(Array.isArray(data) ? data : data.results);
    } catch (error) {
      console.error('Error al cargar categorías:', error);
    }
  };

  const loadProveedores = async () => {
    try {
      const data = await inventarioApi.getProveedores({ is_active: true });
      setProveedores(Array.isArray(data) ? data : data.results);
    } catch (error) {
      console.error('Error al cargar proveedores:', error);
    }
  };

  const loadImpuestos = async () => {
    try {
      const data = await configuracionAPI.obtenerImpuestos();
      const impuestosList = Array.isArray(data) ? data : data?.results ?? [];
      setImpuestos(impuestosList);
      if (impuestosList.length > 0) {
        const impuestoBase =
          impuestosList.find((item) => item.is_active !== false) ?? impuestosList[0];
        if (producto) {
          const porcentajeProducto = normalizeIva(producto.iva_porcentaje);
          const impuestoProducto =
            (porcentajeProducto === '0.00'
              ? impuestosList.find((item) =>
                  item.nombre.toLowerCase().includes('exento')
                )
              : null) ||
            impuestosList.find((item) => {
              const match = item.nombre.match(/(\d+(?:\.\d+)?)/);
              const porcentaje = normalizeIva(match ? match[1] : '0');
              return porcentajeProducto === porcentaje;
            });
          setImpuestoSeleccionado(
            impuestoProducto ? String(impuestoProducto.id) : String(impuestoBase.id)
          );
        } else {
          setImpuestoSeleccionado(String(impuestoBase.id));
        }
      }
    } catch (error) {
      console.error('Error al cargar impuestos:', error);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setFormData(prev => ({ ...prev, [name]: checked }));
    } else if (name === 'iva_porcentaje') {
      setImpuestoSeleccionado(value);
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrors({});

    try {
      const impuestoActual = impuestoOpciones.find(
        (item) => String(item.id) === impuestoSeleccionado
      );
      const porcentajeIva = normalizeIva(impuestoActual?.porcentaje ?? '0');

      const data = {
        ...formData,
        categoria: Number(formData.categoria),
        proveedor: formData.proveedor ? Number(formData.proveedor) : null,
        stock: Number(formData.stock),
        stock_minimo: Number(formData.stock_minimo),
        precio_costo: formData.precio_venta || '0.01',
        precio_venta_minimo: formData.precio_venta_minimo || '0',
        iva_porcentaje: porcentajeIva,
      };

      if (producto) {
        await inventarioApi.updateProducto(producto.id, data);
      } else {
        await inventarioApi.createProducto(data);
      }

      onSuccess();
      onClose();
    } catch (error: any) {
      console.error('Error al guardar producto:', error);
      try {
        const errorData = JSON.parse(error.message);
        setErrors(errorData);
      } catch {
        showNotification({
          message: 'Error al guardar el producto.',
          type: 'error',
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCrearCategoria = async () => {
    if (!nuevaCategoria.trim()) {
      showNotification({ message: 'Ingresa el nombre de la categoría.', type: 'error' });
      return;
    }
    setCreandoCategoria(true);
    try {
      const created = await inventarioApi.createCategoria({
        nombre: nuevaCategoria.trim(),
      });
      await loadCategorias();
      setFormData((prev) => ({ ...prev, categoria: String(created.id) }));
      setNuevaCategoria('');
      setMostrarCategoriaRapida(false);
      showNotification({ message: 'Categoría creada.', type: 'success' });
    } catch (error) {
      console.error('Error al crear categoría:', error);
      showNotification({ message: 'No se pudo crear la categoría.', type: 'error' });
    } finally {
      setCreandoCategoria(false);
    }
  };

  const handleCrearProveedor = async () => {
    if (!nuevoProveedor.trim()) {
      showNotification({ message: 'Ingresa el nombre del proveedor.', type: 'error' });
      return;
    }
    setCreandoProveedor(true);
    try {
      const created = await inventarioApi.createProveedor({
        nombre: nuevoProveedor.trim(),
      });
      await loadProveedores();
      setFormData((prev) => ({ ...prev, proveedor: String(created.id) }));
      setNuevoProveedor('');
      setMostrarProveedorRapido(false);
      showNotification({ message: 'Proveedor creado.', type: 'success' });
    } catch (error) {
      console.error('Error al crear proveedor:', error);
      showNotification({ message: 'No se pudo crear el proveedor.', type: 'error' });
    } finally {
      setCreandoProveedor(false);
    }
  };

  const formattedPrecio = new Intl.NumberFormat('es-CO').format(
    Number(formData.precio_venta || 0)
  );

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white shadow-xl max-w-3xl w-full rounded-md border border-gray-400 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-blue-600 text-white">
          <h2 className="text-sm font-bold uppercase">
            {producto ? 'Actualizar mercancía' : 'Registrar nuevo artículo'}
          </h2>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-100 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Código
              </label>
              <input
                type="text"
                name="codigo"
                value={formData.codigo}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              />
              {errors.codigo && (
                <p className="text-red-500 text-xs mt-1">{errors.codigo}</p>
              )}
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Nombre
              </label>
              <input
                type="text"
                name="nombre"
                value={formData.nombre}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              />
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Categoría
              </label>
              <select
                name="categoria"
                value={formData.categoria}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              >
                <option value="">Seleccione una categoría</option>
                {categorias.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.nombre}
                  </option>
                ))}
              </select>
              <div className="mt-2 rounded border border-dashed border-blue-200 bg-blue-50 px-2 py-2 text-xs text-blue-700">
                <div className="flex items-center justify-between">
                  <span>
                    {categorias.length === 0
                      ? 'No hay categorías registradas.'
                      : '¿No encuentras la categoría?'}
                  </span>
                  <button
                    type="button"
                    onClick={() => setMostrarCategoriaRapida((prev) => !prev)}
                    className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:text-blue-900"
                  >
                    <Plus size={12} /> Agregar rápida
                  </button>
                </div>
                {mostrarCategoriaRapida && (
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="text"
                      value={nuevaCategoria}
                      onChange={(event) => setNuevaCategoria(event.target.value)}
                      placeholder="Nombre de la categoría"
                      className="flex-1 rounded border border-blue-200 bg-white px-2 py-1 text-xs text-slate-700"
                    />
                    <button
                      type="button"
                      onClick={handleCrearCategoria}
                      disabled={creandoCategoria}
                      className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                    >
                      {creandoCategoria ? 'Creando...' : 'Crear'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Proveedor
              </label>
              <select
                name="proveedor"
                value={formData.proveedor}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
              >
                <option value="">Seleccione un proveedor</option>
                {proveedores.map((prov) => (
                  <option key={prov.id} value={prov.id}>
                    {prov.nombre}
                  </option>
                ))}
              </select>
              <div className="mt-2 rounded border border-dashed border-blue-200 bg-blue-50 px-2 py-2 text-xs text-blue-700">
                <div className="flex items-center justify-between">
                  <span>
                    {proveedores.length === 0
                      ? 'No hay proveedores registrados.'
                      : '¿No encuentras el proveedor?'}
                  </span>
                  <button
                    type="button"
                    onClick={() => setMostrarProveedorRapido((prev) => !prev)}
                    className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:text-blue-900"
                  >
                    <Plus size={12} /> Agregar rápida
                  </button>
                </div>
                {mostrarProveedorRapido && (
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="text"
                      value={nuevoProveedor}
                      onChange={(event) => setNuevoProveedor(event.target.value)}
                      placeholder="Nombre del proveedor"
                      className="flex-1 rounded border border-blue-200 bg-white px-2 py-1 text-xs text-slate-700"
                    />
                    <button
                      type="button"
                      onClick={handleCrearProveedor}
                      disabled={creandoProveedor}
                      className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                    >
                      {creandoProveedor ? 'Creando...' : 'Crear'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div>
              <label className="block font-semibold text-gray-800 mb-1">
                U/M
              </label>
              <select
                name="unidad_medida"
                value={formData.unidad_medida}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
              >
                <option value="UND">Unidad</option>
                <option value="PAR">Par</option>
                <option value="KG">Kilogramo</option>
                <option value="LT">Litro</option>
                <option value="MT">Metro</option>
                <option value="N/A">N/A</option>
              </select>
              <p className="text-[11px] text-red-600 mt-1">
                Si el artículo se vende suelto seleccione unidad de medida (UM)
              </p>
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                IVA (%)
              </label>
              <select
                name="iva_porcentaje"
                value={impuestoSeleccionado}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
              >
                {impuestos.length === 0 && (
                  <option value="">Sin impuestos configurados</option>
                )}
                {impuestoOpciones.map((impuesto) => (
                  <option key={impuesto.id} value={String(impuesto.id)}>
                    {impuesto.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Cantidad
              </label>
              <input
                type="number"
                name="stock"
                value={formData.stock}
                onChange={handleChange}
                min="0"
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              />
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Aviso
              </label>
              <input
                type="number"
                name="stock_minimo"
                value={formData.stock_minimo}
                onChange={handleChange}
                min="0"
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              />
            </div>

            <div className="md:col-span-2">
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Estante
              </label>
              <input
                type="text"
                name="descripcion"
                value={formData.descripcion}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                placeholder="Ubicación o estantería"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Precio
              </label>
              <input
                type="number"
                name="precio_venta"
                value={formData.precio_venta}
                onChange={handleChange}
                step="0.01"
                min="0"
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              />
              {errors.precio_costo && (
                <p className="text-red-500 text-xs mt-1">{errors.precio_costo}</p>
              )}
            </div>
            <div className="flex items-end">
              <div className="w-full bg-gray-100 border border-gray-300 rounded px-3 py-2 text-lg font-bold text-gray-900 text-center">
                {formattedPrecio}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                name="aplica_descuento"
                checked={formData.aplica_descuento}
                onChange={handleChange}
                className="w-4 h-4 text-blue-600 rounded"
              />
              Aplica descuento
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                name="es_servicio"
                checked={formData.es_servicio}
                onChange={handleChange}
                className="w-4 h-4 text-blue-600 rounded"
              />
              Es servicio
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
                className="w-4 h-4 text-blue-600 rounded"
              />
              Activo
            </label>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-gray-200">
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-xs font-semibold"
            >
              {loading ? 'Guardando...' : 'Guardar'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1 border border-gray-400 rounded text-gray-700 hover:bg-gray-100 transition-colors text-xs font-semibold"
            >
              Cerrar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
