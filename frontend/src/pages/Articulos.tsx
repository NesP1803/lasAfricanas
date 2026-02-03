import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArchiveX,
  Boxes,
  PackageCheck,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';
import {
  inventarioApi,
  type Categoria,
  type InventarioEstadisticas,
  type PaginatedResponse,
  type Producto,
  type ProductoList,
  type Proveedor,
} from '../api/inventario';
import ProductoForm from '../components/ProductoForm';
import ConfirmModal from '../components/ConfirmModal';
import Pagination from '../components/Pagination';
import { useAuth } from '../contexts/AuthContext';
import { useNotification } from '../contexts/NotificationContext';
import {
  createFullModuleAccess,
  isSectionEnabled,
  normalizeModuleAccess,
} from '../store/moduleAccess';

type ArticulosTab = 'mercancia' | 'stock_bajo';
type EstadoFiltro = 'todos' | 'agotado' | 'bajo' | 'ok';

const PAGE_SIZE = 50;

const tabConfig: Array<{
  key: ArticulosTab;
  label: string;
  description: string;
}> = [
  {
    key: 'mercancia',
    label: 'Mercancía',
    description: 'Catálogo completo de artículos disponibles.',
  },
  {
    key: 'stock_bajo',
    label: 'Stock bajo',
    description: 'Artículos con alerta de inventario.',
  },
];

const currency = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});
const dateFormatter = new Intl.DateTimeFormat('es-CO', {
  dateStyle: 'short',
  timeStyle: 'short',
});

const parseListado = <T,>(data: PaginatedResponse<T> | T[]) => {
  if (Array.isArray(data)) {
    return { items: data, count: data.length };
  }
  return { items: data.results, count: data.count };
};

export default function Articulos() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const isAdmin = user?.role?.toUpperCase() === 'ADMIN';
  const moduleAccess = useMemo(
    () =>
      isAdmin
        ? createFullModuleAccess()
        : normalizeModuleAccess(user?.modulos_permitidos ?? null),
    [isAdmin, user?.modulos_permitidos]
  );

  const allowedTabs = useMemo(
    () => tabConfig.filter((tab) => isSectionEnabled(moduleAccess, 'articulos', tab.key)),
    [moduleAccess]
  );

  const tabParam = searchParams.get('tab');
  const fallbackTab = allowedTabs[0]?.key ?? 'mercancia';
  const activeTab: ArticulosTab = allowedTabs.some((tab) => tab.key === tabParam)
    ? (tabParam as ArticulosTab)
    : fallbackTab;
  const activeTabConfig = useMemo(
    () => allowedTabs.find((tab) => tab.key === activeTab) ?? allowedTabs[0],
    [activeTab, allowedTabs]
  );

  const [estadisticas, setEstadisticas] = useState<InventarioEstadisticas | null>(null);
  const [loading, setLoading] = useState(false);
  const [mercancia, setMercancia] = useState<ProductoList[]>([]);
  const [stockBajo, setStockBajo] = useState<ProductoList[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [search, setSearch] = useState('');
  const [estadoFiltro, setEstadoFiltro] = useState<EstadoFiltro>('todos');
  const [categoriaFiltro, setCategoriaFiltro] = useState('todos');
  const [proveedorFiltro, setProveedorFiltro] = useState('todos');
  const [page, setPage] = useState(1);
  const [totalRegistros, setTotalRegistros] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedResumen, setSelectedResumen] = useState<ProductoList | null>(null);
  const [selectedProducto, setSelectedProducto] = useState<Producto | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [loadingProducto, setLoadingProducto] = useState(false);

  const { showNotification } = useNotification();

  useEffect(() => {
    loadEstadisticas();
    loadFiltros();
  }, []);

  useEffect(() => {
    if (!allowedTabs.some((tab) => tab.key === tabParam)) {
      setSearchParams({ tab: fallbackTab });
    }
  }, [allowedTabs, fallbackTab, setSearchParams, tabParam]);

  useEffect(() => {
    setPage(1);
    setSelectedId(null);
    setSelectedResumen(null);
  }, [activeTab]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (activeTab === 'mercancia') {
        loadMercancia();
      }
      if (activeTab === 'stock_bajo') {
        loadStockBajo();
      }
    }, 350);
    return () => clearTimeout(timeout);
  }, [activeTab, search, page, categoriaFiltro, proveedorFiltro, estadoFiltro]);

  const loadEstadisticas = async () => {
    try {
      const data = await inventarioApi.getEstadisticas();
      setEstadisticas(data);
    } catch (error) {
      console.error('Error al cargar estadísticas:', error);
    }
  };

  const loadFiltros = async () => {
    try {
      const [categoriasData, proveedoresData] = await Promise.all([
        inventarioApi.getCategorias({ is_active: true }),
        inventarioApi.getProveedores({ is_active: true }),
      ]);
      setCategorias(parseListado(categoriasData).items);
      setProveedores(parseListado(proveedoresData).items);
    } catch (error) {
      console.error('Error al cargar filtros:', error);
    }
  };

  const loadMercancia = async () => {
    try {
      setLoading(true);
      const categoria =
        categoriaFiltro !== 'todos' ? Number(categoriaFiltro) : undefined;
      const proveedor =
        proveedorFiltro !== 'todos' ? Number(proveedorFiltro) : undefined;
      const stock_estado = estadoFiltro !== 'todos' ? estadoFiltro : undefined;
      const data = await inventarioApi.getProductos({
        search,
        page,
        categoria,
        proveedor,
        stock_estado,
      });
      setMercancia(data.results);
      setTotalRegistros(data.count);
    } catch (error) {
      console.error('Error al cargar productos:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStockBajo = async () => {
    try {
      setLoading(true);
      const data = await inventarioApi.getStockBajo({ page });
      const parsed = parseListado(data);
      setStockBajo(parsed.items);
      setTotalRegistros(parsed.count);
    } catch (error) {
      console.error('Error al cargar stock bajo:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshCurrent = async () => {
    await loadEstadisticas();
    if (activeTab === 'mercancia') {
      await loadMercancia();
    }
    if (activeTab === 'stock_bajo') {
      await loadStockBajo();
    }
  };

  const openCreate = () => {
    setSelectedProducto(null);
    setModalOpen(true);
  };

  const openEditById = async (id: number, codigo?: string) => {
    try {
      setLoadingProducto(true);
      setSelectedResumen(null);
      try {
        const producto = await inventarioApi.getProducto(id);
        setSelectedProducto(producto);
        setModalOpen(true);
        return;
      } catch (error) {
        if (codigo) {
          const producto = await inventarioApi.buscarPorCodigo(codigo);
          setSelectedProducto(producto);
          setModalOpen(true);
          return;
        }
        throw error;
      }
    } catch (error) {
      console.error('Error al cargar producto:', error);
      showNotification({
        message: 'No se pudo cargar el artículo seleccionado.',
        type: 'error',
      });
    } finally {
      setLoadingProducto(false);
    }
  };

  const openEditFromSelection = async () => {
    if (!selectedId) {
      return;
    }
    const resumen = selectedResumen;
    if (resumen?.id === selectedId) {
      void openEditById(resumen.id, resumen.codigo);
      return;
    }
    const selectedRecord = mercancia.find((producto) => producto.id === selectedId);
    if (selectedRecord) {
      void openEditById(selectedRecord.id, selectedRecord.codigo);
      return;
    }
    void openEditById(selectedId);
  };

  const formatUltimaCompra = (producto: ProductoList) => {
    const lastDate = producto.updated_at ?? producto.created_at;
    if (!lastDate) return 'Sin registro';
    return dateFormatter.format(new Date(lastDate));
  };

  const handleDelete = async () => {
    if (!selectedId) {
      showNotification({
        message: 'Selecciona un artículo para eliminar.',
        type: 'error',
      });
      return;
    }
    setConfirmDeleteOpen(true);
  };

  const confirmDelete = async () => {
    if (!selectedId) return;
    try {
      setLoading(true);
      await inventarioApi.deleteProducto(selectedId);
      setSelectedId(null);
      await refreshCurrent();
      showNotification({
        message: 'Artículo eliminado correctamente.',
        type: 'success',
      });
    } catch (error) {
      console.error('Error al eliminar producto:', error);
      showNotification({
        message: 'No se pudo eliminar el artículo.',
        type: 'error',
      });
    } finally {
      setLoading(false);
      setConfirmDeleteOpen(false);
    }
  };

  const renderEstadoStock = (estado: ProductoList['stock_estado']) => {
    if (estado === 'AGOTADO') {
      return (
        <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
          Agotado
        </span>
      );
    }
    if (estado === 'BAJO') {
      return (
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
          Stock bajo
        </span>
      );
    }
    return (
      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
        OK
      </span>
    );
  };

  const formatStockValue = (stock: string, unidadMedida?: string) => {
    const numeric = Number(stock);
    if (!Number.isFinite(numeric)) {
      return stock;
    }
    if (unidadMedida === 'N/A') {
      return Math.trunc(numeric).toString();
    }
    const hasDecimals = Math.abs(numeric % 1) > 0;
    return hasDecimals ? numeric.toFixed(2) : numeric.toFixed(0);
  };

  const totalPages = Math.max(1, Math.ceil(totalRegistros / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Artículos</h1>
          <p className="text-sm text-gray-500">
            {activeTabConfig.description}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={refreshCurrent}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
          >
            <RefreshCw size={16} />
            Actualizar
          </button>
          <button
            type="button"
            onClick={openEditFromSelection}
            className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!selectedId || loadingProducto}
          >
            <Pencil size={16} />
            Editar
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            <Plus size={16} />
            Nuevo artículo
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="inline-flex items-center gap-2 rounded-md border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-600 shadow-sm transition hover:bg-red-50"
          >
            <Trash2 size={16} />
            Eliminar
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">
                Artículos registrados
              </p>
              <p className="text-2xl font-semibold text-slate-900">
                {estadisticas?.total ?? '--'}
              </p>
            </div>
            <div className="rounded-lg bg-blue-50 p-3 text-blue-600">
              <Boxes size={20} />
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">
                Stock bajo
              </p>
              <p className="text-2xl font-semibold text-amber-600">
                {estadisticas?.stock_bajo ?? '--'}
              </p>
            </div>
            <div className="rounded-lg bg-amber-50 p-3 text-amber-500">
              <AlertTriangle size={20} />
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">
                Agotados
              </p>
              <p className="text-2xl font-semibold text-red-600">
                {estadisticas?.agotados ?? '--'}
              </p>
            </div>
            <div className="rounded-lg bg-red-50 p-3 text-red-500">
              <ArchiveX size={20} />
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-400">
                Cartera inventario
              </p>
              <p className="text-xl font-semibold text-slate-900">
                {estadisticas
                  ? currency.format(Number(estadisticas.valor_inventario))
                  : '--'}
              </p>
            </div>
            <div className="rounded-lg bg-emerald-50 p-3 text-emerald-500">
              <PackageCheck size={20} />
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 pb-4">
        {allowedTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setSearchParams({ tab: tab.key })}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              activeTab === tab.key
                ? 'bg-blue-600 text-white shadow-sm'
                : 'bg-white text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'mercancia' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2">
                <Search size={16} className="text-slate-400" />
                <input
                  type="text"
                  placeholder="Buscar por código o nombre"
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(1);
                  }}
                  className="w-64 bg-transparent text-sm text-slate-700 outline-none"
                />
              </div>
              <select
                value={categoriaFiltro}
                onChange={(event) => {
                  setCategoriaFiltro(event.target.value);
                  setPage(1);
                }}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <option value="todos">Todas las categorías</option>
                {categorias.map((categoria) => (
                  <option key={categoria.id} value={categoria.id}>
                    {categoria.nombre}
                  </option>
                ))}
              </select>
              <select
                value={proveedorFiltro}
                onChange={(event) => {
                  setProveedorFiltro(event.target.value);
                  setPage(1);
                }}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <option value="todos">Todos los proveedores</option>
                {proveedores.map((proveedor) => (
                  <option key={proveedor.id} value={proveedor.id}>
                    {proveedor.nombre}
                  </option>
                ))}
              </select>
              <select
                value={estadoFiltro}
                onChange={(event) => {
                  setEstadoFiltro(event.target.value as EstadoFiltro);
                  setPage(1);
                }}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
              >
                <option value="todos">Todos los estados</option>
                <option value="ok">OK</option>
                <option value="bajo">Stock bajo</option>
                <option value="agotado">Agotado</option>
              </select>
            </div>
            <div className="text-sm text-slate-500">
              Mostrando {mercancia.length} de {totalRegistros} artículos
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Código</th>
                  <th className="px-4 py-3">Artículo</th>
                  <th className="px-4 py-3">Categoría</th>
                  <th className="px-4 py-3">Proveedor</th>
                  <th className="px-4 py-3">Última compra</th>
                  <th className="px-4 py-3 text-right">Precio</th>
                  <th className="px-4 py-3 text-right">Stock</th>
                  <th className="px-4 py-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mercancia.map((producto) => (
                  <tr
                    key={producto.id}
                    onClick={() => {
                      setSelectedId(producto.id);
                      setSelectedResumen(producto);
                    }}
                    onDoubleClick={() => openEditById(producto.id, producto.codigo)}
                    className={`cursor-pointer transition ${
                      selectedId === producto.id
                        ? 'bg-blue-100'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="px-4 py-3 font-medium text-slate-700">
                      {producto.codigo}
                    </td>
                    <td className="px-4 py-3 text-slate-800">{producto.nombre}</td>
                    <td className="px-4 py-3 text-slate-500">
                      {producto.categoria_nombre}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {producto.proveedor_nombre}
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {formatUltimaCompra(producto)}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-700">
                      {currency.format(Number(producto.precio_venta))}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-700">
                      {formatStockValue(producto.stock, producto.unidad_medida)}
                    </td>
                    <td className="px-4 py-3">{renderEstadoStock(producto.stock_estado)}</td>
                  </tr>
                ))}
                {mercancia.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-slate-500">
                      {loading ? 'Cargando artículos...' : 'No hay artículos registrados.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            className="text-slate-500"
          />
        </div>
      )}

      {activeTab === 'stock_bajo' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm text-slate-500">
            <p>Artículos con niveles críticos de inventario.</p>
            <span>Total: {totalRegistros} artículos</span>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Artículo</th>
                  <th className="px-4 py-3">Código</th>
                  <th className="px-4 py-3 text-right">Stock</th>
                  <th className="px-4 py-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {stockBajo.map((producto) => (
                  <tr key={producto.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-700">
                      {producto.nombre}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{producto.codigo}</td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-700">
                      {formatStockValue(producto.stock, producto.unidad_medida)}
                    </td>
                    <td className="px-4 py-3">{renderEstadoStock(producto.stock_estado)}</td>
                  </tr>
                ))}
                {stockBajo.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                      {loading
                        ? 'Cargando artículos...'
                        : 'No hay artículos con stock bajo.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <Pagination
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              className="text-slate-500"
            />
          )}
        </div>
      )}

      {modalOpen && (
        <ProductoForm
          producto={selectedProducto}
          onClose={() => setModalOpen(false)}
          onSuccess={async () => {
            setModalOpen(false);
            await refreshCurrent();
            showNotification({
              message: selectedProducto
                ? 'Artículo actualizado correctamente.'
                : 'Artículo creado correctamente.',
              type: 'success',
            });
          }}
        />
      )}
      <ConfirmModal
        open={confirmDeleteOpen}
        title="Eliminar artículo"
        description="Esta acción eliminará el artículo seleccionado. ¿Deseas continuar?"
        confirmLabel="Eliminar"
        confirmVariant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
        loading={loading}
      />
    </div>
  );
}
