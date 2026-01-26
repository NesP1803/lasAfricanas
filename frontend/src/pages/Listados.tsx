import { useEffect, useMemo, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw,
  Plus,
  Pencil,
  Trash2,
  Search,
  Users,
  Briefcase,
  Tags,
  Truck,
  Wrench,
  X,
} from 'lucide-react';
import { inventarioApi } from '../api/inventario';
import { ventasApi } from '../api/ventas';
import { usuariosApi } from '../api/usuarios';
import { tallerApi, type Mecanico } from '../api/taller';
import type { Categoria, Proveedor } from '../api/inventario';
import type { Cliente, PaginatedResponse, UsuarioAdmin } from '../types';
import { useAuth } from '../contexts/AuthContext';
import ConfirmModal from '../components/ConfirmModal';
import { useNotification } from '../contexts/NotificationContext';
import {
  createFullModuleAccess,
  isSectionEnabled,
  normalizeModuleAccess,
} from '../store/moduleAccess';

type ActiveTab = 'clientes' | 'proveedores' | 'empleados' | 'categorias' | 'mecanicos';

type FormMode = 'create' | 'edit';
type EstadoFiltro = 'activos' | 'inactivos' | 'todos';

type ListadoTab = {
  key: ActiveTab;
  label: string;
  description: string;
  icon: JSX.Element;
};

const tabs: ListadoTab[] = [
  {
    key: 'clientes',
    label: 'Clientes',
    description: 'Gestión de clientes y contactos comerciales.',
    icon: <Users size={18} />,
  },
  {
    key: 'proveedores',
    label: 'Proveedores',
    description: 'Catálogo de proveedores y sus datos clave.',
    icon: <Truck size={18} />,
  },
  {
    key: 'empleados',
    label: 'Empleados',
    description: 'Usuarios internos y roles del sistema.',
    icon: <Briefcase size={18} />,
  },
  {
    key: 'categorias',
    label: 'Categorías',
    description: 'Clasificación de repuestos y servicios.',
    icon: <Tags size={18} />,
  },
  {
    key: 'mecanicos',
    label: 'Mecánicos',
    description: 'Equipo del taller asignado a las motos y reparaciones.',
    icon: <Wrench size={18} />,
  },
];

const documentoOptions = [
  { value: 'CC', label: 'Cédula' },
  { value: 'NIT', label: 'NIT' },
  { value: 'CE', label: 'Cédula de extranjería' },
  { value: 'PASAPORTE', label: 'Pasaporte' },
];

const tipoUsuarioOptions = [
  { value: 'ADMIN', label: 'Administrador' },
  { value: 'VENDEDOR', label: 'Vendedor' },
  { value: 'MECANICO', label: 'Mecánico' },
  { value: 'BODEGUERO', label: 'Bodeguero' },
];

const sedeOptions = [{ value: 'GAIRA', label: 'Gaira - Santa Marta' }];

const parseListado = <T,>(data: PaginatedResponse<T> | T[]) => {
  if (Array.isArray(data)) {
    return { items: data, count: data.length };
  }
  return { items: data.results, count: data.count };
};

const PAGE_SIZE = 50;

export default function Listados() {
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
    () => tabs.filter((tab) => isSectionEnabled(moduleAccess, 'listados', tab.key)),
    [moduleAccess]
  );

  const tabParam = searchParams.get('tab');
  const fallbackTab = allowedTabs[0]?.key ?? 'clientes';
  const activeTab: ActiveTab = allowedTabs.some((tab) => tab.key === tabParam)
    ? (tabParam as ActiveTab)
    : fallbackTab;
  const activeTabConfig = useMemo(
    () => allowedTabs.find((tab) => tab.key === activeTab) ?? allowedTabs[0],
    [activeTab, allowedTabs]
  );

  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [totalRegistros, setTotalRegistros] = useState(0);
  const [page, setPage] = useState(1);
  const [estadoFiltro, setEstadoFiltro] = useState<EstadoFiltro>('activos');
  const [documentoFiltro, setDocumentoFiltro] = useState('todos');
  const [ciudadClienteFiltro, setCiudadClienteFiltro] = useState('todos');
  const [ciudadProveedorFiltro, setCiudadProveedorFiltro] = useState('todos');
  const [rolFiltro, setRolFiltro] = useState('todos');
  const [sedeFiltro, setSedeFiltro] = useState('todos');
  const [productosFiltro, setProductosFiltro] = useState('todos');
  const [ciudadMecanicoFiltro, setCiudadMecanicoFiltro] = useState('todos');

  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [mecanicos, setMecanicos] = useState<Mecanico[]>([]);

  const [modalOpen, setModalOpen] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const { showNotification } = useNotification();

  useEffect(() => {
    setSearch('');
    setSelectedId(null);
    setPage(1);
    setEstadoFiltro('activos');
    setDocumentoFiltro('todos');
    setCiudadClienteFiltro('todos');
    setCiudadProveedorFiltro('todos');
    setRolFiltro('todos');
    setSedeFiltro('todos');
    setProductosFiltro('todos');
    setCiudadMecanicoFiltro('todos');
  }, [activeTab]);

  useEffect(() => {
    if (!allowedTabs.some((tab) => tab.key === tabParam)) {
      setSearchParams({ tab: fallbackTab });
    }
  }, [allowedTabs, fallbackTab, setSearchParams, tabParam]);

  useEffect(() => {
    const delay = setTimeout(() => {
      loadListado();
    }, 350);
    return () => clearTimeout(delay);
  }, [activeTab, search, page, estadoFiltro]);

  const loadListado = async () => {
    try {
      setLoading(true);
      setFormError(null);
      const is_active =
        estadoFiltro === 'todos' ? undefined : estadoFiltro === 'activos';
      if (activeTab === 'clientes') {
        const data = await ventasApi.getClientes({ search, page, is_active });
        const parsed = parseListado(data);
        setClientes(parsed.items);
        setTotalRegistros(parsed.count);
        return;
      }
      if (activeTab === 'proveedores') {
        const data = await inventarioApi.getProveedores({ search, page, is_active });
        const parsed = parseListado(data);
        setProveedores(parsed.items);
        setTotalRegistros(parsed.count);
        return;
      }
      if (activeTab === 'categorias') {
        const data = await inventarioApi.getCategorias({ search, page, is_active });
        const parsed = parseListado(data);
        setCategorias(parsed.items);
        setTotalRegistros(parsed.count);
        return;
      }
      if (activeTab === 'empleados') {
        const data = await usuariosApi.getUsuarios({ search, page, is_active });
        const parsed = parseListado(data);
        setUsuarios(parsed.items);
        setTotalRegistros(parsed.count);
        return;
      }
      if (activeTab === 'mecanicos') {
        const data = await tallerApi.getMecanicos({ search, page, is_active });
        const parsed = parseListado(data);
        setMecanicos(parsed.items);
        setTotalRegistros(parsed.count);
        return;
      }
    } catch (error) {
      console.error('Error al cargar listados:', error);
      setFormError('No se pudieron cargar los listados. Intenta nuevamente.');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = async () => {
    setFormMode('create');
    setFormError(null);
    setFormData(getDefaultFormData(activeTab));
    setModalOpen(true);
  };

  const openEdit = async (record: any) => {
    setFormMode('edit');
    setFormError(null);
    setFormData(getEditFormData(activeTab, record));
    setModalOpen(true);
  };

  const closeModal = () => {
    if (saving) return;
    setModalOpen(false);
    setFormData({});
    setFormError(null);
  };

  const handleDelete = async () => {
    if (!selectedId) {
      showNotification({
        message: 'Selecciona un registro para eliminar.',
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
      if (activeTab === 'clientes') {
        await ventasApi.eliminarCliente(selectedId);
      } else if (activeTab === 'proveedores') {
        await inventarioApi.deleteProveedor(selectedId);
      } else if (activeTab === 'categorias') {
        await inventarioApi.deleteCategoria(selectedId);
      } else if (activeTab === 'empleados') {
        await usuariosApi.deleteUsuario(selectedId);
      } else if (activeTab === 'mecanicos') {
        await tallerApi.deleteMecanico(selectedId);
      }
      setSelectedId(null);
      await loadListado();
      showNotification({
        message: 'Registro eliminado correctamente.',
        type: 'success',
      });
    } catch (error) {
      console.error('Error al eliminar:', error);
      showNotification({
        message: 'No se pudo eliminar el registro.',
        type: 'error',
      });
    } finally {
      setLoading(false);
      setConfirmDeleteOpen(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setFormError(null);

    try {
      const payload = buildPayload(activeTab, formData);
      if (activeTab === 'clientes') {
        if (formMode === 'create') {
          await ventasApi.crearCliente(payload);
        } else {
          await ventasApi.actualizarCliente(formData.id, payload);
        }
      } else if (activeTab === 'proveedores') {
        if (formMode === 'create') {
          await inventarioApi.createProveedor(payload);
        } else {
          await inventarioApi.updateProveedor(formData.id, payload);
        }
      } else if (activeTab === 'categorias') {
        if (formMode === 'create') {
          await inventarioApi.createCategoria(payload);
        } else {
          await inventarioApi.updateCategoria(formData.id, payload);
        }
      } else if (activeTab === 'empleados') {
        if (formMode === 'create') {
          await usuariosApi.createUsuario(payload);
        } else {
          await usuariosApi.updateUsuario(formData.id, payload);
        }
      } else if (activeTab === 'mecanicos') {
        if (formMode === 'create') {
          await tallerApi.createMecanico(payload);
        } else {
          await tallerApi.updateMecanico(formData.id, payload);
        }
      }
      setModalOpen(false);
      setFormData({});
      await loadListado();
      showNotification({
        message:
          formMode === 'create'
            ? 'Registro creado correctamente.'
            : 'Registro actualizado correctamente.',
        type: 'success',
      });
    } catch (error: any) {
      console.error('Error al guardar:', error);
      setFormError('No se pudo guardar la información. Revisa los datos.');
    } finally {
      setSaving(false);
    }
  };

  const handleRowSelect = (id: number) => {
    setSelectedId(id);
  };

  const currentList = useMemo(() => {
    if (activeTab === 'clientes') return clientes;
    if (activeTab === 'proveedores') return proveedores;
    if (activeTab === 'categorias') return categorias;
    if (activeTab === 'empleados') return usuarios;
    if (activeTab === 'mecanicos') return mecanicos;
    return [];
  }, [activeTab, categorias, clientes, proveedores, usuarios, mecanicos]);

  const ciudadesClientes = useMemo(
    () =>
      [...new Set(clientes.map((cliente) => cliente.ciudad).filter(Boolean))].sort(),
    [clientes]
  );
  const ciudadesProveedores = useMemo(
    () =>
      [
        ...new Set(
          proveedores.map((proveedor) => proveedor.ciudad).filter(Boolean)
        ),
      ].sort(),
    [proveedores]
  );
  const rolesUsuarios = useMemo(
    () =>
      [...new Set(usuarios.map((usuario) => usuario.tipo_usuario).filter(Boolean))].sort(),
    [usuarios]
  );
  const sedesUsuarios = useMemo(
    () =>
      [...new Set(usuarios.map((usuario) => usuario.sede).filter(Boolean))].sort(),
    [usuarios]
  );
  const ciudadesMecanicos = useMemo(
    () =>
      [...new Set(mecanicos.map((mecanico) => mecanico.ciudad).filter(Boolean))].sort(),
    [mecanicos]
  );

  const clientesFiltrados = useMemo(() => {
    let filtered = clientes;
    if (documentoFiltro !== 'todos') {
      filtered = filtered.filter(
        (cliente) => cliente.tipo_documento === documentoFiltro
      );
    }
    if (ciudadClienteFiltro !== 'todos') {
      filtered = filtered.filter((cliente) => cliente.ciudad === ciudadClienteFiltro);
    }
    return filtered;
  }, [clientes, ciudadClienteFiltro, documentoFiltro]);

  const proveedoresFiltrados = useMemo(() => {
    if (ciudadProveedorFiltro === 'todos') return proveedores;
    return proveedores.filter(
      (proveedor) => proveedor.ciudad === ciudadProveedorFiltro
    );
  }, [proveedores, ciudadProveedorFiltro]);

  const categoriasFiltradas = useMemo(() => {
    if (productosFiltro === 'todos') return categorias;
    if (productosFiltro === 'con_productos') {
      return categorias.filter((categoria) => categoria.total_productos > 0);
    }
    return categorias.filter((categoria) => categoria.total_productos === 0);
  }, [categorias, productosFiltro]);

  const usuariosFiltrados = useMemo(() => {
    let filtered = usuarios;
    if (rolFiltro !== 'todos') {
      filtered = filtered.filter((usuario) => usuario.tipo_usuario === rolFiltro);
    }
    if (sedeFiltro !== 'todos') {
      filtered = filtered.filter((usuario) => usuario.sede === sedeFiltro);
    }
    return filtered;
  }, [usuarios, rolFiltro, sedeFiltro]);

  const mecanicosFiltrados = useMemo(() => {
    if (ciudadMecanicoFiltro === 'todos') return mecanicos;
    return mecanicos.filter(
      (mecanico) => mecanico.ciudad === ciudadMecanicoFiltro
    );
  }, [mecanicos, ciudadMecanicoFiltro]);

  const registrosFiltrados = useMemo(() => {
    if (activeTab === 'clientes') return clientesFiltrados.length;
    if (activeTab === 'proveedores') return proveedoresFiltrados.length;
    if (activeTab === 'categorias') return categoriasFiltradas.length;
    if (activeTab === 'empleados') return usuariosFiltrados.length;
    if (activeTab === 'mecanicos') return mecanicosFiltrados.length;
    return currentList.length;
  }, [
    activeTab,
    categoriasFiltradas.length,
    clientesFiltrados.length,
    currentList.length,
    mecanicosFiltrados.length,
    proveedoresFiltrados.length,
    usuariosFiltrados.length,
  ]);

  const searchPlaceholder = useMemo(() => {
    if (activeTab === 'clientes') return 'Buscar por nombre, documento o teléfono...';
    if (activeTab === 'proveedores') return 'Buscar por proveedor, NIT o ciudad...';
    if (activeTab === 'categorias') return 'Buscar por nombre o descripción...';
    if (activeTab === 'empleados') return 'Buscar por usuario, nombre o rol...';
    if (activeTab === 'mecanicos') return 'Buscar por nombre, teléfono o ciudad...';
    return 'Buscar...';
  }, [activeTab]);

  const totalPages = Math.max(1, Math.ceil(totalRegistros / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase text-blue-500">Listados</p>
            <h1 className="text-xl font-semibold text-slate-900">
              {activeTabConfig.label}
            </h1>
            <p className="text-sm text-slate-500">
              {activeTabConfig.description}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={loadListado}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:text-blue-600"
            >
              <RefreshCw size={16} />
              Actualizar
            </button>
            <button
              type="button"
              onClick={openCreate}
              className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
            >
              <Plus size={16} />
              Nuevo registro
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 border-b border-slate-200 bg-slate-50 px-6 py-3">
          {allowedTabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setSearchParams({ tab: tab.key })}
              className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white shadow'
                  : 'border border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:text-blue-600'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div className="flex flex-1 flex-wrap items-center gap-3">
            <div className="flex flex-1 items-center gap-3 rounded-full border border-slate-200 bg-white px-4 py-2 shadow-sm">
              <Search size={16} className="text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder={searchPlaceholder}
                className="flex-1 bg-transparent text-sm text-slate-700 outline-none"
              />
            </div>
            <select
              value={estadoFiltro}
              onChange={(event) => {
                setEstadoFiltro(event.target.value as EstadoFiltro);
                setPage(1);
              }}
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
            >
              <option value="activos">Activos</option>
              <option value="inactivos">Inactivos</option>
              <option value="todos">Todos</option>
            </select>
            {activeTab === 'clientes' && (
              <>
                <select
                  value={documentoFiltro}
                  onChange={(event) => setDocumentoFiltro(event.target.value)}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
                >
                  <option value="todos">Todos los documentos</option>
                  {documentoOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <select
                  value={ciudadClienteFiltro}
                  onChange={(event) => setCiudadClienteFiltro(event.target.value)}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
                >
                  <option value="todos">Todas las ciudades</option>
                  {ciudadesClientes.map((ciudad) => (
                    <option key={ciudad} value={ciudad}>
                      {ciudad}
                    </option>
                  ))}
                </select>
              </>
            )}
            {activeTab === 'proveedores' && (
              <select
                value={ciudadProveedorFiltro}
                onChange={(event) => setCiudadProveedorFiltro(event.target.value)}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
              >
                <option value="todos">Todas las ciudades</option>
                {ciudadesProveedores.map((ciudad) => (
                  <option key={ciudad} value={ciudad}>
                    {ciudad}
                  </option>
                ))}
              </select>
            )}
            {activeTab === 'empleados' && (
              <>
                <select
                  value={rolFiltro}
                  onChange={(event) => setRolFiltro(event.target.value)}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
                >
                  <option value="todos">Todos los roles</option>
                  {rolesUsuarios.map((rol) => (
                    <option key={rol} value={rol}>
                      {rol}
                    </option>
                  ))}
                </select>
                <select
                  value={sedeFiltro}
                  onChange={(event) => setSedeFiltro(event.target.value)}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
                >
                  <option value="todos">Todas las sedes</option>
                  {sedesUsuarios.map((sede) => (
                    <option key={sede} value={sede}>
                      {sede}
                    </option>
                  ))}
                </select>
              </>
            )}
            {activeTab === 'categorias' && (
              <select
                value={productosFiltro}
                onChange={(event) => setProductosFiltro(event.target.value)}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
              >
                <option value="todos">Todas las categorías</option>
                <option value="con_productos">Con productos</option>
                <option value="sin_productos">Sin productos</option>
              </select>
            )}
            {activeTab === 'mecanicos' && (
              <select
                value={ciudadMecanicoFiltro}
                onChange={(event) => setCiudadMecanicoFiltro(event.target.value)}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm"
              >
                <option value="todos">Todas las ciudades</option>
                {ciudadesMecanicos.map((ciudad) => (
                  <option key={ciudad} value={ciudad}>
                    {ciudad}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              Mostrando {registrosFiltrados} de {totalRegistros} registros
            </span>
            <span className="text-xs text-slate-400">
              Doble clic sobre un registro para editar
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-6 py-3">
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-100"
          >
            <Plus size={14} />
            Registrar
          </button>
          <button
            type="button"
            onClick={() => {
              const selectedRecord = currentList.find(
                (record: any) => record.id === selectedId
              );
              if (!selectedRecord) {
                showNotification({
                  message: 'Selecciona un registro para editar.',
                  type: 'error',
                });
                return;
              }
              openEdit(selectedRecord);
            }}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-600"
          >
            <Pencil size={14} />
            Editar
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-600 transition hover:bg-rose-100"
          >
            <Trash2 size={14} />
            Eliminar
          </button>
        </div>

        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-sm text-slate-500">
              Cargando información...
            </div>
          ) : registrosFiltrados === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              No hay registros para mostrar.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                {renderTableHeader(activeTab)}
              </thead>
              <tbody className="divide-y divide-slate-200">
                {renderTableRows({
                  activeTab,
                  clientes: clientesFiltrados,
                  proveedores: proveedoresFiltrados,
                  categorias: categoriasFiltradas,
                  usuarios: usuariosFiltrados,
                  mecanicos: mecanicosFiltrados,
                  selectedId,
                  onSelect: handleRowSelect,
                  onDoubleClick: openEdit,
                })}
              </tbody>
            </table>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4 text-sm text-slate-500">
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

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
          <div className="w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-blue-500">
                  {formMode === 'create' ? 'Nuevo' : 'Editar'} {activeTabConfig.label}
                </p>
                <h2 className="text-lg font-semibold text-slate-900">
                  {formMode === 'create'
                    ? 'Registrar información'
                    : 'Actualizar información'}
                </h2>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-6 px-6 py-4">
              {formError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                  {formError}
                </div>
              )}
              {renderFormFields(activeTab, formData, setFormData)}
              <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded-full border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:border-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-full bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {saving ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      <ConfirmModal
        open={confirmDeleteOpen}
        title="Eliminar registro"
        description="Esta acción eliminará el registro seleccionado. ¿Deseas continuar?"
        confirmLabel="Eliminar"
        confirmVariant="danger"
        onConfirm={confirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
        loading={loading}
      />
    </div>
  );
}

const getDefaultFormData = (tab: ActiveTab) => {
  if (tab === 'clientes') {
    return {
      tipo_documento: 'CC',
      numero_documento: '',
      nombre: '',
      telefono: '',
      email: '',
      direccion: '',
      ciudad: '',
      is_active: true,
    };
  }
  if (tab === 'proveedores') {
    return {
      nombre: '',
      nit: '',
      telefono: '',
      email: '',
      direccion: '',
      ciudad: '',
      contacto: '',
      is_active: true,
    };
  }
  if (tab === 'categorias') {
    return {
      nombre: '',
      descripcion: '',
      orden: 0,
      is_active: true,
    };
  }
  if (tab === 'empleados') {
    return {
      username: '',
      email: '',
      first_name: '',
      last_name: '',
      tipo_usuario: 'VENDEDOR',
      telefono: '',
      sede: '',
      is_active: true,
      password: '',
    };
  }
  if (tab === 'mecanicos') {
    return {
      nombre: '',
      telefono: '',
      email: '',
      direccion: '',
      ciudad: '',
      is_active: true,
    };
  }
  return {};
};

const getEditFormData = (tab: ActiveTab, record: any) => {
  if (tab === 'clientes') {
    return {
      id: record.id,
      tipo_documento: record.tipo_documento,
      numero_documento: record.numero_documento,
      nombre: record.nombre,
      telefono: record.telefono ?? '',
      email: record.email ?? '',
      direccion: record.direccion ?? '',
      ciudad: record.ciudad ?? '',
      is_active: record.is_active,
    };
  }
  if (tab === 'proveedores') {
    return {
      id: record.id,
      nombre: record.nombre,
      nit: record.nit ?? '',
      telefono: record.telefono ?? '',
      email: record.email ?? '',
      direccion: record.direccion ?? '',
      ciudad: record.ciudad ?? '',
      contacto: record.contacto ?? '',
      is_active: record.is_active,
    };
  }
  if (tab === 'categorias') {
    return {
      id: record.id,
      nombre: record.nombre,
      descripcion: record.descripcion ?? '',
      orden: record.orden ?? 0,
      is_active: record.is_active,
    };
  }
  if (tab === 'empleados') {
    return {
      id: record.id,
      username: record.username,
      email: record.email ?? '',
      first_name: record.first_name ?? '',
      last_name: record.last_name ?? '',
      tipo_usuario: record.tipo_usuario ?? 'VENDEDOR',
      telefono: record.telefono ?? '',
      sede: record.sede ?? '',
      is_active: record.is_active,
      password: '',
    };
  }
  if (tab === 'mecanicos') {
    return {
      id: record.id,
      nombre: record.nombre,
      telefono: record.telefono ?? '',
      email: record.email ?? '',
      direccion: record.direccion ?? '',
      ciudad: record.ciudad ?? '',
      is_active: record.is_active,
    };
  }
  return {};
};

const buildPayload = (tab: ActiveTab, data: Record<string, any>) => {
  if (tab === 'categorias') {
    return {
      nombre: data.nombre,
      descripcion: data.descripcion,
      orden: Number(data.orden) || 0,
      is_active: data.is_active,
    };
  }
  if (tab === 'empleados') {
    const payload: Record<string, any> = {
      username: data.username,
      email: data.email,
      first_name: data.first_name,
      last_name: data.last_name,
      tipo_usuario: data.tipo_usuario,
      telefono: data.telefono,
      sede: data.sede,
      is_active: data.is_active,
    };
    if (data.password) {
      payload.password = data.password;
    }
    return payload;
  }
  if (tab === 'clientes') {
    return {
      tipo_documento: data.tipo_documento,
      numero_documento: data.numero_documento,
      nombre: data.nombre,
      telefono: data.telefono,
      email: data.email,
      direccion: data.direccion,
      ciudad: data.ciudad,
      is_active: data.is_active,
    };
  }
  if (tab === 'mecanicos') {
    return {
      nombre: data.nombre,
      telefono: data.telefono,
      email: data.email,
      direccion: data.direccion,
      ciudad: data.ciudad,
      is_active: data.is_active,
    };
  }
  return {
    nombre: data.nombre,
    nit: data.nit,
    telefono: data.telefono,
    email: data.email,
    direccion: data.direccion,
    ciudad: data.ciudad,
    contacto: data.contacto,
    is_active: data.is_active,
  };
};

const renderTableHeader = (tab: ActiveTab) => {
  if (tab === 'clientes') {
    return (
      <tr>
        <th className="px-4 py-3">Documento</th>
        <th className="px-4 py-3">Nombre</th>
        <th className="px-4 py-3">Ciudad</th>
        <th className="px-4 py-3">Teléfono</th>
        <th className="px-4 py-3">Email</th>
        <th className="px-4 py-3">Estado</th>
      </tr>
    );
  }
  if (tab === 'proveedores') {
    return (
      <tr>
        <th className="px-4 py-3">Proveedor</th>
        <th className="px-4 py-3">NIT</th>
        <th className="px-4 py-3">Contacto</th>
        <th className="px-4 py-3">Ciudad</th>
        <th className="px-4 py-3">Teléfono</th>
        <th className="px-4 py-3">Estado</th>
      </tr>
    );
  }
  if (tab === 'categorias') {
    return (
      <tr>
        <th className="px-4 py-3">Categoría</th>
        <th className="px-4 py-3">Descripción</th>
        <th className="px-4 py-3">Orden</th>
        <th className="px-4 py-3">Productos</th>
        <th className="px-4 py-3">Estado</th>
      </tr>
    );
  }
  if (tab === 'empleados') {
    return (
      <tr>
        <th className="px-4 py-3">Usuario</th>
        <th className="px-4 py-3">Nombre</th>
        <th className="px-4 py-3">Rol</th>
        <th className="px-4 py-3">Teléfono</th>
        <th className="px-4 py-3">Sede</th>
        <th className="px-4 py-3">Estado</th>
      </tr>
    );
  }
  if (tab === 'mecanicos') {
    return (
      <tr>
        <th className="px-4 py-3">Mecánico</th>
        <th className="px-4 py-3">Teléfono</th>
        <th className="px-4 py-3">Email</th>
        <th className="px-4 py-3">Ciudad</th>
        <th className="px-4 py-3">Estado</th>
      </tr>
    );
  }
  return null;
};

const renderTableRows = ({
  activeTab,
  clientes,
  proveedores,
  categorias,
  usuarios,
  mecanicos,
  selectedId,
  onSelect,
  onDoubleClick,
}: {
  activeTab: ActiveTab;
  clientes: Cliente[];
  proveedores: Proveedor[];
  categorias: Categoria[];
  usuarios: UsuarioAdmin[];
  mecanicos: Mecanico[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDoubleClick: (record: any) => void;
}) => {
  const baseRowClasses = (isSelected: boolean) =>
    `cursor-pointer transition ${
      isSelected ? 'bg-blue-100' : 'hover:bg-slate-50'
    }`;

  if (activeTab === 'clientes') {
    return clientes.map((cliente) => (
      <tr
        key={cliente.id}
        className={baseRowClasses(cliente.id === selectedId)}
        onClick={() => onSelect(cliente.id)}
        onDoubleClick={() => onDoubleClick(cliente)}
      >
        <td className="px-4 py-3 font-medium text-slate-800">
          {cliente.tipo_documento} {cliente.numero_documento}
        </td>
        <td className="px-4 py-3">{cliente.nombre}</td>
        <td className="px-4 py-3">{cliente.ciudad || '—'}</td>
        <td className="px-4 py-3">{cliente.telefono || '—'}</td>
        <td className="px-4 py-3">{cliente.email || '—'}</td>
        <td className="px-4 py-3">
          <EstadoBadge activo={cliente.is_active} />
        </td>
      </tr>
    ));
  }

  if (activeTab === 'proveedores') {
    return proveedores.map((proveedor) => (
      <tr
        key={proveedor.id}
        className={baseRowClasses(proveedor.id === selectedId)}
        onClick={() => onSelect(proveedor.id)}
        onDoubleClick={() => onDoubleClick(proveedor)}
      >
        <td className="px-4 py-3 font-medium text-slate-800">
          {proveedor.nombre}
        </td>
        <td className="px-4 py-3">{proveedor.nit || '—'}</td>
        <td className="px-4 py-3">{proveedor.contacto || '—'}</td>
        <td className="px-4 py-3">{proveedor.ciudad || '—'}</td>
        <td className="px-4 py-3">{proveedor.telefono || '—'}</td>
        <td className="px-4 py-3">
          <EstadoBadge activo={proveedor.is_active} />
        </td>
      </tr>
    ));
  }

  if (activeTab === 'categorias') {
    return categorias.map((categoria) => (
      <tr
        key={categoria.id}
        className={baseRowClasses(categoria.id === selectedId)}
        onClick={() => onSelect(categoria.id)}
        onDoubleClick={() => onDoubleClick(categoria)}
      >
        <td className="px-4 py-3 font-medium text-slate-800">
          {categoria.nombre}
        </td>
        <td className="px-4 py-3">{categoria.descripcion || '—'}</td>
        <td className="px-4 py-3">{categoria.orden}</td>
        <td className="px-4 py-3">{categoria.total_productos}</td>
        <td className="px-4 py-3">
          <EstadoBadge activo={categoria.is_active} />
        </td>
      </tr>
    ));
  }

  if (activeTab === 'empleados') {
    return usuarios.map((usuario) => (
      <tr
        key={usuario.id}
        className={baseRowClasses(usuario.id === selectedId)}
        onClick={() => onSelect(usuario.id)}
        onDoubleClick={() => onDoubleClick(usuario)}
      >
        <td className="px-4 py-3 font-medium text-slate-800">
          {usuario.username}
        </td>
        <td className="px-4 py-3">
          {`${usuario.first_name ?? ''} ${usuario.last_name ?? ''}`.trim() ||
            '—'}
        </td>
        <td className="px-4 py-3">{usuario.tipo_usuario}</td>
        <td className="px-4 py-3">{usuario.telefono || '—'}</td>
        <td className="px-4 py-3">{usuario.sede || '—'}</td>
        <td className="px-4 py-3">
          <EstadoBadge activo={usuario.is_active} />
        </td>
      </tr>
    ));
  }

  if (activeTab === 'mecanicos') {
    return mecanicos.map((mecanico) => (
      <tr
        key={mecanico.id}
        className={baseRowClasses(mecanico.id === selectedId)}
        onClick={() => onSelect(mecanico.id)}
        onDoubleClick={() => onDoubleClick(mecanico)}
      >
        <td className="px-4 py-3 font-medium text-slate-800">
          {mecanico.nombre}
        </td>
        <td className="px-4 py-3">{mecanico.telefono || '—'}</td>
        <td className="px-4 py-3">{mecanico.email || '—'}</td>
        <td className="px-4 py-3">{mecanico.ciudad || '—'}</td>
        <td className="px-4 py-3">
          <EstadoBadge activo={mecanico.is_active} />
        </td>
      </tr>
    ));
  }

  return null;
};

const EstadoBadge = ({ activo }: { activo: boolean }) => (
  <span
    className={`rounded-full px-2 py-1 text-xs font-semibold ${
      activo ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
    }`}
  >
    {activo ? 'Activo' : 'Inactivo'}
  </span>
);

const renderFormFields = (
  tab: ActiveTab,
  formData: Record<string, any>,
  setFormData: Dispatch<SetStateAction<Record<string, any>>>
) => {
  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value, type } = event.target;
    if (type === 'checkbox') {
      const checked = (event.target as HTMLInputElement).checked;
      setFormData((prev) => ({ ...prev, [name]: checked }));
    } else {
      setFormData((prev) => ({ ...prev, [name]: value }));
    }
  };

  if (tab === 'clientes') {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <SelectField
          label="Tipo de documento"
          name="tipo_documento"
          value={formData.tipo_documento}
          onChange={handleChange}
          options={documentoOptions}
          required
        />
        <InputField
          label="Número de documento"
          name="numero_documento"
          value={formData.numero_documento}
          onChange={handleChange}
          required
        />
        <InputField
          label="Nombre / Razón social"
          name="nombre"
          value={formData.nombre}
          onChange={handleChange}
          required
        />
        <InputField
          label="Teléfono"
          name="telefono"
          value={formData.telefono}
          onChange={handleChange}
        />
        <InputField
          label="Email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
        />
        <InputField
          label="Ciudad"
          name="ciudad"
          value={formData.ciudad}
          onChange={handleChange}
        />
        <TextAreaField
          label="Dirección"
          name="direccion"
          value={formData.direccion}
          onChange={handleChange}
        />
        <CheckboxField
          label="Cliente activo"
          name="is_active"
          checked={formData.is_active}
          onChange={handleChange}
        />
      </div>
    );
  }

  if (tab === 'proveedores') {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <InputField
          label="Nombre del proveedor"
          name="nombre"
          value={formData.nombre}
          onChange={handleChange}
          required
        />
        <InputField
          label="NIT"
          name="nit"
          value={formData.nit}
          onChange={handleChange}
        />
        <InputField
          label="Teléfono"
          name="telefono"
          value={formData.telefono}
          onChange={handleChange}
        />
        <InputField
          label="Email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
        />
        <InputField
          label="Ciudad"
          name="ciudad"
          value={formData.ciudad}
          onChange={handleChange}
        />
        <InputField
          label="Contacto"
          name="contacto"
          value={formData.contacto}
          onChange={handleChange}
        />
        <TextAreaField
          label="Dirección"
          name="direccion"
          value={formData.direccion}
          onChange={handleChange}
        />
        <CheckboxField
          label="Proveedor activo"
          name="is_active"
          checked={formData.is_active}
          onChange={handleChange}
        />
      </div>
    );
  }

  if (tab === 'categorias') {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <InputField
          label="Nombre de la categoría"
          name="nombre"
          value={formData.nombre}
          onChange={handleChange}
          required
        />
        <InputField
          label="Orden"
          name="orden"
          type="number"
          value={formData.orden}
          onChange={handleChange}
        />
        <TextAreaField
          label="Descripción"
          name="descripcion"
          value={formData.descripcion}
          onChange={handleChange}
        />
        <CheckboxField
          label="Categoría activa"
          name="is_active"
          checked={formData.is_active}
          onChange={handleChange}
        />
      </div>
    );
  }

  if (tab === 'empleados') {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <InputField
          label="Usuario"
          name="username"
          value={formData.username}
          onChange={handleChange}
          required
        />
        <InputField
          label="Email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
        />
        <InputField
          label="Nombre"
          name="first_name"
          value={formData.first_name}
          onChange={handleChange}
        />
        <InputField
          label="Apellido"
          name="last_name"
          value={formData.last_name}
          onChange={handleChange}
        />
        <SelectField
          label="Tipo de usuario"
          name="tipo_usuario"
          value={formData.tipo_usuario}
          onChange={handleChange}
          options={tipoUsuarioOptions}
          required
        />
        <SelectField
          label="Sede"
          name="sede"
          value={formData.sede}
          onChange={handleChange}
          options={sedeOptions}
          placeholder="Seleccionar sede"
        />
        <InputField
          label="Teléfono"
          name="telefono"
          value={formData.telefono}
          onChange={handleChange}
        />
        <InputField
          label="Contraseña (opcional)"
          name="password"
          type="password"
          value={formData.password}
          onChange={handleChange}
          placeholder="Nueva contraseña"
        />
        <CheckboxField
          label="Usuario activo"
          name="is_active"
          checked={formData.is_active}
          onChange={handleChange}
        />
      </div>
    );
  }

  if (tab === 'mecanicos') {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <InputField
          label="Nombre del mecánico"
          name="nombre"
          value={formData.nombre}
          onChange={handleChange}
          required
        />
        <InputField
          label="Teléfono"
          name="telefono"
          value={formData.telefono}
          onChange={handleChange}
        />
        <InputField
          label="Email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
        />
        <InputField
          label="Ciudad"
          name="ciudad"
          value={formData.ciudad}
          onChange={handleChange}
        />
        <TextAreaField
          label="Dirección"
          name="direccion"
          value={formData.direccion}
          onChange={handleChange}
        />
        <CheckboxField
          label="Mecánico activo"
          name="is_active"
          checked={formData.is_active}
          onChange={handleChange}
        />
      </div>
    );
  }

  return null;
};

const InputField = ({
  label,
  name,
  value,
  onChange,
  type = 'text',
  required,
  placeholder,
}: {
  label: string;
  name: string;
  value: any;
  onChange: React.ChangeEventHandler<HTMLInputElement>;
  type?: string;
  required?: boolean;
  placeholder?: string;
}) => (
  <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
    {label}
    <input
      type={type}
      name={name}
      value={value}
      onChange={onChange}
      required={required}
      placeholder={placeholder}
      className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
    />
  </label>
);

const SelectField = ({
  label,
  name,
  value,
  onChange,
  options,
  placeholder,
  required,
}: {
  label: string;
  name: string;
  value: any;
  onChange: React.ChangeEventHandler<HTMLSelectElement>;
  options: { value: string; label: string }[];
  placeholder?: string;
  required?: boolean;
}) => (
  <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
    {label}
    <select
      name={name}
      value={value}
      onChange={onChange}
      required={required}
      className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  </label>
);

const TextAreaField = ({
  label,
  name,
  value,
  onChange,
}: {
  label: string;
  name: string;
  value: any;
  onChange: React.ChangeEventHandler<HTMLTextAreaElement>;
}) => (
  <label className="flex flex-col gap-2 text-sm font-medium text-slate-700 md:col-span-2">
    {label}
    <textarea
      name={name}
      value={value}
      onChange={onChange}
      rows={3}
      className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
    />
  </label>
);

const CheckboxField = ({
  label,
  name,
  checked,
  onChange,
}: {
  label: string;
  name: string;
  checked: boolean;
  onChange: React.ChangeEventHandler<HTMLInputElement>;
}) => (
  <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
    <input
      type="checkbox"
      name={name}
      checked={checked}
      onChange={onChange}
      className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-200"
    />
    {label}
  </label>
);
