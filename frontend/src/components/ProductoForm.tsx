import { useState, useEffect } from 'react';
import { X, HelpCircle, Info } from 'lucide-react';
import { inventarioApi } from '../api/inventario';
import { configuracionAPI } from '../api/configuracion';
import type { Producto, Categoria, Proveedor} from "../api/inventario";
import type { Impuesto } from '../types';


interface ProductoFormProps {
  producto?: Producto | null;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ProductoForm({ producto, onClose, onSuccess }: ProductoFormProps) {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [impuestos, setImpuestos] = useState<Impuesto[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<any>({});

  const [formData, setFormData] = useState({
    codigo: '',
    nombre: '',
    descripcion: '',
    categoria: '',
    proveedor: '',
    precio_costo: '',
    precio_venta: '',
    precio_venta_minimo: '',
    stock: '0',
    stock_minimo: '5',
    unidad_medida: 'UND',
    iva_porcentaje: '19',
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
        proveedor: producto.proveedor.toString(),
        precio_costo: producto.precio_costo,
        precio_venta: producto.precio_venta,
        precio_venta_minimo: producto.precio_venta_minimo,
        stock: producto.stock.toString(),
        stock_minimo: producto.stock_minimo.toString(),
        unidad_medida: producto.unidad_medida,
        iva_porcentaje: producto.iva_porcentaje,
        aplica_descuento: producto.aplica_descuento,
        es_servicio: producto.es_servicio,
        is_active: producto.is_active,
      });
    }
  }, [producto]);

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
      if (!producto && impuestosList.length > 0) {
        const impuestoBase =
          impuestosList.find((item) => item.is_active !== false) ?? impuestosList[0];
        const porcentaje =
          impuestoBase.porcentaje ?? (impuestoBase.valor && impuestoBase.valor !== 'E'
            ? impuestoBase.valor
            : '0');
        setFormData((prev) => ({ ...prev, iva_porcentaje: porcentaje ?? '0' }));
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
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrors({});

    try {
      const data = {
        ...formData,
        categoria: Number(formData.categoria),
        proveedor: Number(formData.proveedor),
        stock: Number(formData.stock),
        stock_minimo: Number(formData.stock_minimo),
        precio_costo: formData.precio_costo || "0",
        precio_venta_minimo: formData.precio_venta_minimo || "0",
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
        alert('Error al guardar el producto');
      }
    } finally {
      setLoading(false);
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
                Código *
                <HelpCircle size={14} className="text-gray-500" />
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
                Nombre *
                <HelpCircle size={14} className="text-gray-500" />
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
                Categoría *
                <HelpCircle size={14} className="text-gray-500" />
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
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Proveedor *
                <HelpCircle size={14} className="text-gray-500" />
              </label>
              <select
                name="proveedor"
                value={formData.proveedor}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
                required
              >
                <option value="">Seleccione un proveedor</option>
                {proveedores.map((prov) => (
                  <option key={prov.id} value={prov.id}>
                    {prov.nombre}
                  </option>
                ))}
              </select>
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
              </select>
              <p className="text-[11px] text-red-600 mt-1">
                Si el artículo se vende suelto seleccione unidad de medida (UM)
              </p>
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                IVA (%)
                <HelpCircle size={14} className="text-gray-500" />
              </label>
              <select
                name="iva_porcentaje"
                value={formData.iva_porcentaje}
                onChange={handleChange}
                className="w-full px-2 py-1 border border-gray-400 rounded bg-white"
              >
                {impuestos.length === 0 && (
                  <option value="">Sin impuestos configurados</option>
                )}
                {impuestos.map((impuesto) => {
                  const porcentaje =
                    impuesto.porcentaje ??
                    (impuesto.valor && impuesto.valor !== 'E' ? impuesto.valor : '0');
                  const label = impuesto.es_exento
                    ? `${impuesto.nombre} (Exento)`
                    : `${impuesto.nombre} ${porcentaje ?? '0'}%`;
                  return (
                    <option key={impuesto.id} value={porcentaje ?? '0'}>
                      {label}
                    </option>
                  );
                })}
              </select>
            </div>

            <div>
              <label className="flex items-center gap-2 font-semibold text-gray-800 mb-1">
                Cantidad *
                <HelpCircle size={14} className="text-gray-500" />
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
                Aviso *
                <HelpCircle size={14} className="text-gray-500" />
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
                <HelpCircle size={14} className="text-gray-500" />
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
                Precio *
                <HelpCircle size={14} className="text-gray-500" />
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

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-gray-200">
            <button
              type="button"
              className="px-3 py-1 border border-gray-400 rounded text-gray-700 hover:bg-gray-100 transition-colors text-xs font-semibold flex items-center gap-2"
            >
              <Info size={14} />
              Ayuda
            </button>
            <div className="flex items-center gap-2">
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
          </div>
        </form>
      </div>
    </div>
  );
}
