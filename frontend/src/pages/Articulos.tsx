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
import { useAuth } from '../contexts/AuthContext';
import {
  createFullModuleAccess,
  isSectionEnabled,
  normalizeModuleAccess,
} from '../store/moduleAccess';

type ArticulosTab = 'mercancia' | 'stock_bajo' |  'dar_de_baja';
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
  {
    key: 'dar_de_baja',
    label: 'Dar de baja',
    description: 'Registra salidas por daños o pérdidas.',
  },
];

const currency = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
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
  const [loadingProducto, setLoadingProducto] = useState(false);

  const [codigoBaja, setCodigoBaja] = useState('');
  const [productoBaja, setProductoBaja] = useState<Producto | null>(null);
  const [cantidadBaja, setCantidadBaja] = useState('');
  const [motivoBaja, setMotivoBaja] = useState('');
  const [bajaError, setBajaError] = useState<string | null>(null);

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
      const data = await inventarioApi.getProductos({
        search,
        page,
        categoria,
        proveedor,
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
      alert('No se pudo cargar el artículo seleccionado.');
    } finally {
      setLoadingProducto(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) {
      alert('Selecciona un artículo para eliminar.');
      return;
    }
    if (!confirm('¿Deseas eliminar este artículo?')) return;

    try {
      setLoading(true);
      await inventarioApi.deleteProducto(selectedId);
      setSelectedId(null);
      await refreshCurrent();
    } catch (error) {
      console.error('Error al eliminar producto:', error);
      alert('No se pudo eliminar el artículo.');
    } finally {
      setLoading(false);
    }
  };

  const handleBuscarBaja = async () => {
    if (!codigoBaja.trim()) return;
    try {
      setBajaError(null);
      const producto = await inventarioApi.buscarPorCodigo(codigoBaja.trim());
      setProductoBaja(producto);
    } catch (error) {
      console.error('Error al buscar producto:', error);
      setProductoBaja(null);
      setBajaError('No se encontró el código ingresado.');
    }
  };

  const handleRegistrarBaja = async () => {
    if (!productoBaja) {
      setBajaError('Busca un artículo válido.');
      return;
    }
    const cantidad = Number(cantidadBaja);
    if (!cantidad || cantidad <= 0) {
      setBajaError('Ingresa una cantidad válida.');
      return;
    }
    if (!motivoBaja.trim()) {
      setBajaError('Indica el motivo de la baja.');
      return;
    }

    try {
      setLoading(true);
      await inventarioApi.ajustarStock(productoBaja.id, {
        cantidad,
        tipo: 'BAJA',
        costo_unitario: productoBaja.precio_costo ?? '0',
        observaciones: motivoBaja,
      });
      setCodigoBaja('');
      setProductoBaja(null);
      setCantidadBaja('');
      setMotivoBaja('');
      setBajaError(null);
      await refreshCurrent();
    } catch (error) {
      console.error('Error al dar de baja:', error);
      setBajaError('No se pudo registrar la baja.');
    } finally {
      setLoading(false);
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

  const totalPages = Math.max(1, Math.ceil(totalRegistros / PAGE_SIZE));
  const mercanciaFiltrada = mercancia.filter((producto) => {
    if (estadoFiltro === 'todos') return true;
    if (estadoFiltro === 'agotado') return producto.stock_estado === 'AGOTADO';
    if (estadoFiltro === 'bajo') return producto.stock_estado === 'BAJO';
    return producto.stock_estado === 'OK';
  });

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
            onClick={() => {
              if (selectedResumen) {
                void openEditById(selectedResumen.id, selectedResumen.codigo);
                return;
              }
              if (selectedId) {
                void openEditById(selectedId);
              }
            }}
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
              Total: {totalRegistros} artículos
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
                  <th className="px-4 py-3 text-right">Precio</th>
                  <th className="px-4 py-3 text-right">Stock</th>
                  <th className="px-4 py-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mercanciaFiltrada.map((producto) => (
                  <tr
                    key={producto.id}
                    onClick={() => {
                      setSelectedId(producto.id);
                      setSelectedResumen(producto);
                    }}
                    onDoubleClick={() => openEditById(producto.id, producto.codigo)}
                    className={`cursor-pointer transition ${
                      selectedId === producto.id
                        ? 'bg-blue-50'
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
                    <td className="px-4 py-3 text-right font-semibold text-slate-700">
                      {currency.format(Number(producto.precio_venta))}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-700">
                      {producto.stock}
                    </td>
                    <td className="px-4 py-3">{renderEstadoStock(producto.stock_estado)}</td>
                  </tr>
                ))}
                {mercanciaFiltrada.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                      {loading ? 'Cargando artículos...' : 'No hay artículos registrados.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-slate-500">
            <button
              type="button"
              disabled={page === 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-50"
            >
              Anterior
            </button>
            <span>
              Página {page} de {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((prev) => prev + 1)}
              className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-50"
            >
              Siguiente
            </button>
          </div>
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
                      {producto.stock}
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
            <div className="flex items-center justify-between text-sm text-slate-500">
              <button
                type="button"
                disabled={page === 1}
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-50"
              >
                Anterior
              </button>
              <span>
                Página {page} de {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((prev) => prev + 1)}
                className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-50"
              >
                Siguiente
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'dar_de_baja' && (
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">
              Dar de baja artículos
            </h2>
            <p className="text-sm text-slate-500">
              Registra salidas por daños, pérdidas u obsequios.
            </p>

            <div className="mt-6 space-y-4">
              <div>
                <label className="text-sm font-semibold text-slate-700">
                  Código del artículo
                </label>
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    value={codigoBaja}
                    onChange={(event) => setCodigoBaja(event.target.value)}
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                    placeholder="Ingresa el código"
                  />
                  <button
                    type="button"
                    onClick={handleBuscarBaja}
                    className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
                  >
                    <Search size={16} />
                    Buscar
                  </button>
                </div>
              </div>

              {productoBaja && (
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-4 text-sm text-slate-700">
                  <p className="font-semibold">{productoBaja.nombre}</p>
                  <p className="text-slate-500">Código: {productoBaja.codigo}</p>
                  <p className="text-slate-500">Stock actual: {productoBaja.stock}</p>
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-semibold text-slate-700">
                    Cantidad a dar de baja
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={cantidadBaja}
                    onChange={(event) => setCantidadBaja(event.target.value)}
                    className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="text-sm font-semibold text-slate-700">
                    Motivo
                  </label>
                  <input
                    type="text"
                    value={motivoBaja}
                    onChange={(event) => setMotivoBaja(event.target.value)}
                    className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                    placeholder="Daños, pérdidas, obsequios..."
                  />
                </div>
              </div>

              {bajaError && (
                <p className="text-sm font-semibold text-red-600">{bajaError}</p>
              )}

              <button
                type="button"
                onClick={handleRegistrarBaja}
                className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-red-700"
              >
                <ArchiveX size={16} />
                Registrar baja
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">
              Recomendaciones
            </h3>
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              <li className="flex items-start gap-2">
                <span className="mt-1 h-2 w-2 rounded-full bg-amber-400" />
                Verifica el stock antes de dar de baja artículos sensibles.
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 h-2 w-2 rounded-full bg-blue-400" />
                Agrega siempre un motivo para mantener el historial ordenado.
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1 h-2 w-2 rounded-full bg-emerald-400" />
                Los movimientos se registran en el backend para auditoría.
              </li>
            </ul>
          </div>
        </div>
      )}

      {modalOpen && (
        <ProductoForm
          producto={selectedProducto}
          onClose={() => setModalOpen(false)}
          onSuccess={async () => {
            setModalOpen(false);
            await refreshCurrent();
          }}
        />
      )}
    </div>
  );
}
