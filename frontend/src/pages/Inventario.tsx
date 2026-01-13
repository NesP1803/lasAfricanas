import { useMemo, useState, useEffect } from "react";
import {
  Plus,
  Filter,
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
  const [stockBajo, setStockBajo] = useState<ProductoList[]>([]);
  const [loadingStockBajo, setLoadingStockBajo] = useState(true);
  const [bajaCodigo, setBajaCodigo] = useState("");
  const [bajaCantidad, setBajaCantidad] = useState(1);
  const [bajaMotivo, setBajaMotivo] = useState("Daños");
  const [bajaItems, setBajaItems] = useState<
    { id: number; codigo: string; nombre: string; cantidad: number; motivo: string; stockActual: number }[]
  >([]);
  const [savingBaja, setSavingBaja] = useState(false);
  
  // Estados para el formulario
  const [showForm, setShowForm] = useState(false);
  const [selectedProducto, setSelectedProducto] = useState<Producto | null>(null);

  useEffect(() => {
    loadCategorias();
    loadProductos();
    loadStockBajo();
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

  const loadStockBajo = async () => {
    try {
      setLoadingStockBajo(true);
      const data = await inventarioApi.getStockBajo();
      setStockBajo(data);
    } catch (error) {
      console.error("Error al cargar stock bajo:", error);
    } finally {
      setLoadingStockBajo(false);
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

  const agotadosItems = useMemo(
    () => productos.filter((p) => p.stock_estado === "AGOTADO"),
    [productos]
  );

  const inventoryValue = useMemo(() => {
    return productos.reduce((acc, producto) => {
      const precio = Number.parseFloat(producto.precio_venta || "0");
      const stock = Number(producto.stock || 0);
      if (Number.isNaN(precio) || Number.isNaN(stock)) return acc;
      return acc + precio * stock;
    }, 0);
  }, [productos]);

  const handleAgregarBaja = async () => {
    if (!bajaCodigo.trim()) return;
    try {
      const match = await inventarioApi.buscarPorCodigo(bajaCodigo.trim());
      setBajaItems((prev) => [
        ...prev,
        {
          id: match.id,
          codigo: match.codigo,
          nombre: match.nombre,
          cantidad: bajaCantidad,
          motivo: bajaMotivo,
          stockActual: match.stock,
        },
      ]);
      setBajaCodigo("");
      setBajaCantidad(1);
      setBajaMotivo("Daños");
    } catch (error) {
      console.error("Error al buscar artículo:", error);
      alert("No se encontró el artículo con ese código.");
    }
  };

  const handleRemoveBaja = (index: number) => {
    setBajaItems((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleGuardarBaja = async () => {
    if (bajaItems.length === 0) return;
    setSavingBaja(true);
    try {
      for (const item of bajaItems) {
        const nuevoStock = item.stockActual - item.cantidad;
        if (nuevoStock < 0) {
          alert(`La cantidad supera el stock disponible para ${item.codigo}.`);
          setSavingBaja(false);
          return;
        }
        await inventarioApi.updateProducto(item.id, {
          stock: nuevoStock,
          is_active: nuevoStock === 0 ? false : true,
        });
      }
      setBajaItems([]);
      loadProductos();
      loadStockBajo();
    } catch (error) {
      console.error("Error al dar de baja artículos:", error);
      alert("No se pudieron guardar las bajas.");
    } finally {
      setSavingBaja(false);
    }
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
    <div className="space-y-5">
      <section className="bg-gradient-to-b from-gray-200 to-gray-300 border border-gray-400 rounded-md p-2 shadow-sm">
        <div className="flex items-center justify-between border-b border-gray-400 pb-2">
          <h2 className="text-sm font-bold text-gray-800 uppercase">
            Listado de artículos (CRUD)
          </h2>
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
          </div>
        </div>
      </section>

      <section className="bg-white border border-gray-400 rounded-md overflow-hidden">
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
            <div className="bg-gray-100 border-t border-gray-300 px-3 py-2 text-xs text-gray-700 flex flex-wrap gap-4">
              <span>
                Artículos registrados: <strong>{productos.length}</strong>
              </span>
              <span>
                Stock bajo: <strong>{stockBajo.length}</strong>
              </span>
              <span>
                Agotados: <strong>{agotadosItems.length}</strong>
              </span>
              <span>
                Cartera de inventario:{" "}
                <strong>${Math.round(inventoryValue).toLocaleString("es-CO")}</strong>
              </span>
            </div>
          </>
        )}
      </section>

      <section className="bg-white border border-gray-400 rounded-md overflow-hidden">
        <div className="bg-gradient-to-b from-blue-500 to-blue-600 text-white text-xs font-bold uppercase px-3 py-2">
          Artículos con stock bajo
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-yellow-300 border-b border-gray-400">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Artículo
                </th>
                <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                  Stock
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loadingStockBajo ? (
                <tr>
                  <td className="px-3 py-3 text-center text-gray-500" colSpan={2}>
                    Cargando stock bajo...
                  </td>
                </tr>
              ) : stockBajo.length === 0 ? (
                <tr>
                  <td className="px-3 py-3 text-center text-gray-500" colSpan={2}>
                    No hay artículos con stock bajo.
                  </td>
                </tr>
              ) : (
                stockBajo.map((producto) => (
                  <tr key={producto.id} className="hover:bg-blue-50">
                    <td className="px-3 py-2 text-gray-900">{producto.nombre}</td>
                    <td className="px-3 py-2 text-gray-900">{producto.stock}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-white border border-gray-400 rounded-md overflow-hidden">
        <div className="bg-gradient-to-b from-blue-500 to-blue-600 text-white text-xs font-bold uppercase px-3 py-2">
          Dar de baja artículos del sistema
        </div>
        <div className="p-3 space-y-3 text-xs">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="min-w-[180px]">
              <label className="font-bold text-gray-800 block mb-1">
                Digite código de artículo
              </label>
              <input
                type="text"
                value={bajaCodigo}
                onChange={(event) => setBajaCodigo(event.target.value)}
                className="w-full px-2 py-1 border border-gray-400 rounded text-sm text-gray-900"
                placeholder="Ej: 00075"
              />
            </div>
            <div className="min-w-[120px]">
              <label className="font-bold text-gray-800 block mb-1">Cant.</label>
              <input
                type="number"
                min={1}
                value={bajaCantidad}
                onChange={(event) => setBajaCantidad(Number(event.target.value))}
                className="w-full px-2 py-1 border border-gray-400 rounded text-sm text-gray-900"
              />
            </div>
            <div className="min-w-[240px]">
              <label className="font-bold text-gray-800 block mb-1">Motivo</label>
              <select
                value={bajaMotivo}
                onChange={(event) => setBajaMotivo(event.target.value)}
                className="w-full px-2 py-1 border border-gray-400 rounded text-sm text-gray-900"
              >
                <option value="Daños">Daños</option>
                <option value="Pérdidas">Pérdidas</option>
                <option value="Obsequios">Obsequios</option>
                <option value="Devolución proveedor">Devolución proveedor</option>
              </select>
            </div>
            <button
              type="button"
              onClick={handleAgregarBaja}
              className="px-3 py-1 border border-gray-400 rounded bg-white text-gray-800 text-xs font-semibold hover:bg-gray-100"
            >
              Agregar
            </button>
            <button
              type="button"
              onClick={handleGuardarBaja}
              disabled={savingBaja}
              className="ml-auto px-3 py-1 border border-gray-400 rounded bg-white text-gray-800 text-xs font-semibold hover:bg-gray-100 disabled:opacity-50"
            >
              {savingBaja ? "Guardando..." : "Guardar"}
            </button>
            <button
              type="button"
              className="px-3 py-1 border border-gray-400 rounded bg-white text-gray-800 text-xs font-semibold hover:bg-gray-100"
            >
              Ayuda
            </button>
          </div>

          <div className="overflow-x-auto border border-gray-300 rounded">
            <table className="w-full text-sm">
              <thead className="bg-yellow-300 border-b border-gray-400">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                    Código
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                    Producto
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                    Cant.
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-bold text-gray-900 uppercase tracking-wider">
                    Motivo
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-bold text-gray-900 uppercase tracking-wider">
                    Acción
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {bajaItems.length === 0 ? (
                  <tr>
                    <td className="px-3 py-4 text-center text-gray-500" colSpan={5}>
                      No hay artículos en baja.
                    </td>
                  </tr>
                ) : (
                  bajaItems.map((item, index) => (
                    <tr key={`${item.codigo}-${index}`} className="hover:bg-blue-50">
                      <td className="px-3 py-2 text-gray-900">{item.codigo}</td>
                      <td className="px-3 py-2 text-gray-900">{item.nombre}</td>
                      <td className="px-3 py-2 text-gray-900">{item.cantidad}</td>
                      <td className="px-3 py-2 text-gray-900">{item.motivo}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => handleRemoveBaja(index)}
                          className="text-red-600 hover:text-red-900"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

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
