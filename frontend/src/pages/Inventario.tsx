import { useState, useEffect } from "react";
import {
  Plus,
  Filter,
  Download,
  Edit,
  Trash2,
  HelpCircle,
  X,
  RefreshCw,
  Minus,
} from "lucide-react";
import { inventarioApi } from "../api/inventario";
import type { ProductoList, Producto, Categoria } from "../api/inventario";
import ProductoForm from '../components/ProductoForm';

export default function Inventario() {
  const [productos, setProductos] = useState<ProductoList[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoriaFilter, setCategoriaFilter] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Estados para el formulario
  const [showForm, setShowForm] = useState(false);
  const [selectedProducto, setSelectedProducto] = useState<Producto | null>(null);

  useEffect(() => {
    loadCategorias();
    loadProductos();
  }, [page, search, categoriaFilter]);

  const loadCategorias = async () => {
    try {
      const data = await inventarioApi.getCategorias();
      setCategorias(Array.isArray(data) ? data : data.results);
    } catch (error) {
      console.error("Error al cargar categorías:", error);
    }
  };

  const loadProductos = async () => {
    try {
      setLoading(true);
      const params: any = { page };
      if (search) params.search = search;
      if (categoriaFilter) params.categoria = categoriaFilter;

      const data = await inventarioApi.getProductos(params);
      setProductos(data.results);
      setTotalPages(Math.ceil(data.count / 100));
    } catch (error) {
      console.error("Error al cargar productos:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const handleCategoriaFilter = (categoriaId: number | null) => {
    setCategoriaFilter(categoriaId);
    setPage(1);
  };

  const handleCreate = () => {
    setSelectedProducto(null);
    setShowForm(true);
  };

  const handleEdit = async (id: number) => {
    try {
      const producto = await inventarioApi.getProducto(id);
      setSelectedProducto(producto);
      setShowForm(true);
    } catch (error) {
      console.error('Error al cargar producto:', error);
      alert('Error al cargar el producto');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Está seguro de eliminar este producto?')) return;

    try {
      await inventarioApi.deleteProducto(id);
      loadProductos();
    } catch (error) {
      console.error('Error al eliminar producto:', error);
      alert('Error al eliminar el producto');
    }
  };

  const handleFormSuccess = () => {
    loadProductos();
  };

  const getStockBadge = (estado: string) => {
    if (estado === "AGOTADO") {
      return (
        <span className="px-2 py-1 text-xs font-semibold rounded bg-red-100 text-red-700">
          Agotado
        </span>
      );
    }
    if (estado === "BAJO") {
      return (
        <span className="px-2 py-1 text-xs font-semibold rounded bg-yellow-100 text-yellow-700">
          Stock Bajo
        </span>
      );
    }
    return (
      <span className="px-2 py-1 text-xs font-semibold rounded bg-green-100 text-green-700">
        Disponible
      </span>
    );
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-gradient-to-b from-gray-200 to-gray-300 border border-gray-400 rounded-md p-2">
        <div className="flex items-center justify-between border-b border-gray-400 pb-2">
          <h1 className="text-sm font-bold text-gray-800 uppercase">
            Listado de artículos
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCreate}
              className="flex items-center gap-2 px-3 py-1 text-xs font-semibold bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              <Plus size={16} />
              Registrar nuevo artículo
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2 text-xs">
          <div className="flex items-center gap-1">
            <ToolbarButton icon={<HelpCircle size={14} />} />
            <ToolbarButton icon={<X size={14} />} />
            <ToolbarButton icon={<RefreshCw size={14} />} />
            <ToolbarButton icon={<Minus size={14} />} />
            <ToolbarButton icon={<Plus size={14} />} />
          </div>

          <div className="flex flex-wrap items-end gap-2 flex-1">
            <div className="min-w-[200px]">
              <label className="font-bold text-gray-800 block mb-1">
                Repuesto
              </label>
              <input
                type="text"
                placeholder="Buscar por nombre..."
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full px-2 py-1 border border-gray-400 rounded text-sm text-gray-900 bg-white"
              />
            </div>

            <div className="min-w-[160px]">
              <label className="font-bold text-gray-800 block mb-1">
                Código
              </label>
              <input
                type="text"
                placeholder="Buscar por código..."
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full px-2 py-1 border border-gray-400 rounded text-sm text-gray-900 bg-white"
              />
            </div>

            <div className="min-w-[180px] relative">
              <label className="font-bold text-gray-800 block mb-1">
                Categoría
              </label>
              <Filter
                className="absolute left-2 top-[30px] text-gray-500"
                size={16}
              />
              <select
                value={categoriaFilter || ""}
                onChange={(e) =>
                  handleCategoriaFilter(
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="w-full pl-7 pr-2 py-1 border border-gray-400 rounded text-sm text-gray-900 bg-white appearance-none"
              >
                <option value="">Todas las categorías</option>
                {categorias.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div className="min-w-[180px]">
              <label className="font-bold text-gray-800 block mb-1">
                Proveedor
              </label>
              <input
                type="text"
                placeholder="Proveedor..."
                className="w-full px-2 py-1 border border-gray-400 rounded text-sm text-gray-900 bg-white"
                disabled
              />
            </div>

            <button className="flex items-center justify-center gap-2 px-3 py-1 border border-gray-400 rounded bg-white text-gray-800 text-xs font-semibold hover:bg-gray-100 transition-colors">
              <Download size={16} />
              Exportar
            </button>
          </div>
        </div>
      </div>

      {/* Products Table */}
      <div className="bg-white border border-gray-400 rounded-md overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            Cargando productos...
          </div>
        ) : productos.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No se encontraron productos
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-yellow-300 border-b border-gray-400">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Código
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Artículo
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Categoría
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Proveedor
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Precio
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Stock
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Ubicación
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Estado
                    </th>
                    <th className="px-3 py-2 text-center text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Inv
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-bold text-gray-900 uppercase tracking-wider">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200 text-sm">
                  {productos.map((producto) => (
                    <tr key={producto.id} className="hover:bg-blue-50">
                      <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                        {producto.codigo}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-gray-900">
                        {producto.nombre}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-gray-700">
                        {producto.categoria_nombre}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-gray-700">
                        {producto.proveedor_nombre}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm font-semibold text-gray-900">
                        $
                        {parseFloat(producto.precio_venta).toLocaleString(
                          "es-CO"
                        )}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                        {producto.stock}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-gray-700">
                        {producto.descripcion || "-"}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        {getStockBadge(producto.stock_estado)}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-center text-gray-700">
                        {producto.is_active ? "*" : "-"}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => handleEdit(producto.id)}
                          className="text-blue-600 hover:text-blue-900 mr-3"
                        >
                          <Edit size={18} />
                        </button>
                        <button
                          onClick={() => handleDelete(producto.id)}
                          className="text-red-600 hover:text-red-900"
                        >
                          <Trash2 size={18} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="px-3 py-2 border-t border-gray-200 flex items-center justify-between text-sm">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="px-3 py-1 border border-gray-400 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                >
                  Anterior
                </button>
                <span className="text-sm text-gray-700">
                  Página {page} de {totalPages}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                  className="px-3 py-1 border border-gray-400 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                >
                  Siguiente
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <div className="bg-gray-100 border border-gray-400 rounded-md px-3 py-1 text-xs text-gray-700 flex flex-wrap gap-4">
        <span>
          Artículos registrados: <strong>{productos.length}</strong>
        </span>
        <span>
          Stock bajo:{" "}
          <strong>
            {productos.filter((p) => p.stock_estado === "BAJO").length}
          </strong>
        </span>
        <span>
          Agotados:{" "}
          <strong>
            {productos.filter((p) => p.stock_estado === "AGOTADO").length}
          </strong>
        </span>
      </div>

      {/* Modal de formulario */}
      {showForm && (
        <ProductoForm
          producto={selectedProducto}
          onClose={() => setShowForm(false)}
          onSuccess={handleFormSuccess}
        />
      )}
    </div>
  );
}

function ToolbarButton({ icon }: { icon: React.ReactNode }) {
  return (
    <button className="w-7 h-7 flex items-center justify-center border border-gray-400 rounded bg-white text-gray-700 hover:bg-gray-100">
      {icon}
    </button>
  );
}
