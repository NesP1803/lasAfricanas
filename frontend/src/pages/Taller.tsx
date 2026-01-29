import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  RefreshCw,
  Plus,
  Search,
  Wrench,
  Bike,
  PackageCheck,
  Trash2,
  Pencil,
  X,
} from 'lucide-react';
import { inventarioApi, type ProductoList } from '../api/inventario';
import { ventasApi } from '../api/ventas';
import { tallerApi, type Mecanico, type Moto, type OrdenTaller } from '../api/taller';
import type { Cliente, PaginatedResponse } from '../types';
import type { Proveedor } from '../api/inventario';
import { useAuth } from '../contexts/AuthContext';
import ConfirmModal from '../components/ConfirmModal';
import { useNotification } from '../contexts/NotificationContext';
import {
  createFullModuleAccess,
  isSectionEnabled,
  normalizeModuleAccess,
} from '../store/moduleAccess';

const parseListado = <T,>(data: PaginatedResponse<T> | T[]) => {
  if (Array.isArray(data)) {
    return { items: data, count: data.length };
  }
  return { items: data.results, count: data.count };
};

type ActiveTab = 'ordenes' | 'motos';

const tabs = [
  {
    key: 'ordenes' as const,
    label: 'Operaciones de taller',
    description: 'Gestiona los mecánicos, motos asociadas y repuestos por orden.',
    icon: <Wrench size={18} />,
  },
  {
    key: 'motos' as const,
    label: 'Registro de motos',
    description: 'Crea, edita y asigna motos a mecánicos y proveedores.',
    icon: <Bike size={18} />,
  },
];

type FormMode = 'create' | 'edit';

type MotoFormData = {
  id?: number;
  placa: string;
  marca: string;
  modelo: string;
  color: string;
  anio: string;
  cliente: string;
  mecanico: string;
  proveedor: string;
  observaciones: string;
  is_active: boolean;
};

type ClienteFormData = {
  tipo_documento: Cliente['tipo_documento'];
  numero_documento: string;
  nombre: string;
  telefono: string;
  email: string;
  direccion: string;
  ciudad: string;
  is_active: boolean;
};

const documentoOptions = [
  { value: 'CC', label: 'Cédula' },
  { value: 'NIT', label: 'NIT' },
  { value: 'CE', label: 'Cédula de extranjería' },
  { value: 'PASAPORTE', label: 'Pasaporte' },
];

const createDefaultMotoForm = (): MotoFormData => ({
  placa: '',
  marca: '',
  modelo: '',
  color: '',
  anio: '',
  cliente: '',
  mecanico: '',
  proveedor: '',
  observaciones: '',
  is_active: true,
});

const createDefaultClienteForm = (): ClienteFormData => ({
  tipo_documento: 'CC',
  numero_documento: '',
  nombre: '',
  telefono: '',
  email: '',
  direccion: '',
  ciudad: '',
  is_active: true,
});

export default function Taller() {
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
    () => tabs.filter((tab) => isSectionEnabled(moduleAccess, 'taller', tab.key)),
    [moduleAccess]
  );

  const tabParam = searchParams.get('tab');
  const fallbackTab = allowedTabs[0]?.key ?? 'ordenes';
  const activeTab: ActiveTab = allowedTabs.some((tab) => tab.key === tabParam)
    ? (tabParam as ActiveTab)
    : fallbackTab;
  const activeTabConfig = useMemo(
    () => allowedTabs.find((tab) => tab.key === activeTab) ?? allowedTabs[0],
    [activeTab, allowedTabs]
  );

  const [loading, setLoading] = useState(false);
  const [mecanicos, setMecanicos] = useState<Mecanico[]>([]);
  const [selectedMecanicoId, setSelectedMecanicoId] = useState<number | null>(null);
  const [motosPorMecanico, setMotosPorMecanico] = useState<Moto[]>([]);
  const [selectedMotoId, setSelectedMotoId] = useState<number | null>(null);
  const [ordenActual, setOrdenActual] = useState<OrdenTaller | null>(null);
  const [searchRepuesto, setSearchRepuesto] = useState('');
  const [repuestos, setRepuestos] = useState<ProductoList[]>([]);
  const [cantidades, setCantidades] = useState<Record<number, number>>({});
  const [facturando, setFacturando] = useState(false);
  const [confirmFacturarOpen, setConfirmFacturarOpen] = useState(false);
  const [repuestoModalOpen, setRepuestoModalOpen] = useState(false);

  const [motosListado, setMotosListado] = useState<Moto[]>([]);
  const [searchMoto, setSearchMoto] = useState('');
  const [selectedMotoListId, setSelectedMotoListId] = useState<number | null>(null);
  const [motoModalOpen, setMotoModalOpen] = useState(false);
  const [motoFormMode, setMotoFormMode] = useState<FormMode>('create');
  const [motoFormData, setMotoFormData] = useState<MotoFormData>(createDefaultMotoForm());
  const [motoFormError, setMotoFormError] = useState<string | null>(null);
  const [savingMoto, setSavingMoto] = useState(false);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [clienteSearch, setClienteSearch] = useState('');
  const [showClienteForm, setShowClienteForm] = useState(false);
  const [clienteFormData, setClienteFormData] = useState<ClienteFormData>(
    createDefaultClienteForm()
  );
  const [clienteFormError, setClienteFormError] = useState<string | null>(null);
  const [savingCliente, setSavingCliente] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const { showNotification } = useNotification();

  useEffect(() => {
    loadMecanicos();
  }, []);

  useEffect(() => {
    if (!allowedTabs.some((tab) => tab.key === tabParam)) {
      setSearchParams({ tab: fallbackTab });
    }
  }, [allowedTabs, fallbackTab, setSearchParams, tabParam]);

  useEffect(() => {
    if (activeTab !== 'ordenes') return;
    if (!selectedMecanicoId && mecanicos.length > 0) {
      setSelectedMecanicoId(mecanicos[0].id);
    }
  }, [activeTab, mecanicos, selectedMecanicoId]);

  useEffect(() => {
    if (activeTab !== 'ordenes') return;
    if (!selectedMecanicoId) {
      setMotosPorMecanico([]);
      return;
    }
    loadMotosPorMecanico(selectedMecanicoId);
  }, [activeTab, selectedMecanicoId]);

  useEffect(() => {
    if (activeTab !== 'ordenes') return;
    const delay = setTimeout(() => {
      if (!searchRepuesto) {
        setRepuestos([]);
        return;
      }
      buscarRepuestos(searchRepuesto);
    }, 300);
    return () => clearTimeout(delay);
  }, [searchRepuesto, activeTab]);

  useEffect(() => {
    if (activeTab !== 'motos') return;
    const delay = setTimeout(() => {
      loadMotosListado();
    }, 300);
    return () => clearTimeout(delay);
  }, [activeTab, searchMoto]);

  const loadMecanicos = async () => {
    try {
      setLoading(true);
      const data = await tallerApi.getMecanicos({ is_active: true });
      const parsed = parseListado(data);
      setMecanicos(parsed.items);
    } catch (error) {
      console.error('Error al cargar mecánicos:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMotosPorMecanico = async (mecanicoId: number) => {
    try {
      setLoading(true);
      const data = await tallerApi.getMotos({ mecanico: mecanicoId });
      const parsed = parseListado(data);
      setMotosPorMecanico(parsed.items);
      if (parsed.items.length > 0) {
        setSelectedMotoId((prev) => prev ?? parsed.items[0].id);
      }
    } catch (error) {
      console.error('Error al cargar motos:', error);
    } finally {
      setLoading(false);
    }
  };

  const buscarRepuestos = async (texto: string) => {
    try {
      const data = await inventarioApi.getProductos({ search: texto });
      const parsed = parseListado(data);
      setRepuestos(parsed.items);
    } catch (error) {
      console.error('Error al buscar repuestos:', error);
    }
  };

  const ensureOrden = async (motoId: number, mecanicoId: number) => {
    const data = await tallerApi.getOrdenes({ moto: motoId });
    const parsed = parseListado(data);
    const abierta = parsed.items.find((orden) => orden.estado !== 'FACTURADO');
    if (abierta) return abierta;
    return tallerApi.createOrden({ moto: motoId, mecanico: mecanicoId, estado: 'EN_PROCESO' });
  };

  const handleSelectMoto = async (moto: Moto) => {
    if (!selectedMecanicoId) return;
    setSelectedMotoId(moto.id);
    try {
      setLoading(true);
      const orden = await ensureOrden(moto.id, selectedMecanicoId);
      setOrdenActual(orden);
    } catch (error) {
      console.error('Error al cargar orden:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAgregarRepuesto = async (productoId: number) => {
    if (!ordenActual) {
      showNotification({
        message: 'Selecciona una moto para crear una orden.',
        type: 'error',
      });
      return;
    }
    const cantidad = cantidades[productoId] ?? 1;
    try {
      const orden = await tallerApi.agregarRepuesto(ordenActual.id, {
        producto: productoId,
        cantidad,
      });
      let ordenFinal = orden;
      try {
        const data = await tallerApi.getOrdenes({ moto: orden.moto });
        const parsed = parseListado(data);
        ordenFinal = parsed.items.find((item) => item.id === orden.id) ?? orden;
      } catch (refreshError) {
        console.error('Error al refrescar la orden:', refreshError);
      }
      setOrdenActual(ordenFinal);
      if (searchRepuesto) {
        await buscarRepuestos(searchRepuesto);
      }
      setCantidades((prev) => ({ ...prev, [productoId]: 1 }));
      setRepuestoModalOpen(false);
      showNotification({
        message: 'Repuesto agregado correctamente.',
        type: 'success',
      });
    } catch (error) {
      console.error('Error al agregar repuesto:', error);
      showNotification({
        message: 'No se pudo agregar el repuesto.',
        type: 'error',
      });
    }
  };

  const handleBuscarRepuestos = async () => {
    if (!searchRepuesto) {
      setRepuestos([]);
      return;
    }
    await buscarRepuestos(searchRepuesto);
  };

  const closeRepuestoModal = () => {
    setRepuestoModalOpen(false);
  };

  const handleEditMotoSeleccionada = async () => {
    const selected = motosPorMecanico.find((moto) => moto.id === selectedMotoId);
    if (!selected) {
      showNotification({
        message: 'Selecciona una moto para editar.',
        type: 'error',
      });
      return;
    }
    await openEditMoto(selected);
  };

  const handleQuitarRepuesto = async (repuestoId: number) => {
    if (!ordenActual) return;
    try {
      const orden = await tallerApi.quitarRepuesto(ordenActual.id, { repuesto_id: repuestoId });
      let ordenFinal = orden;
      try {
        const data = await tallerApi.getOrdenes({ moto: orden.moto });
        const parsed = parseListado(data);
        ordenFinal = parsed.items.find((item) => item.id === orden.id) ?? orden;
      } catch (refreshError) {
        console.error('Error al refrescar la orden:', refreshError);
      }
      setOrdenActual(ordenFinal);
      if (searchRepuesto) {
        await buscarRepuestos(searchRepuesto);
      }
      showNotification({
        message: 'Repuesto eliminado correctamente.',
        type: 'success',
      });
    } catch (error) {
      console.error('Error al quitar repuesto:', error);
      showNotification({
        message: 'No se pudo quitar el repuesto.',
        type: 'error',
      });
    }
  };

  const handleFacturar = async () => {
    if (!ordenActual) return;
    setConfirmFacturarOpen(true);
  };

  const confirmFacturar = async () => {
    if (!ordenActual) return;
    try {
      setFacturando(true);
      const orden = await tallerApi.facturarOrden(ordenActual.id, { tipo_comprobante: 'REMISION' });
      setOrdenActual(orden);
      showNotification({
        message: 'Orden enviada a facturación.',
        type: 'success',
      });
    } catch (error: any) {
      console.error('Error al facturar:', error);
      showNotification({
        message: error?.message || 'No se pudo facturar la orden.',
        type: 'error',
      });
    } finally {
      setFacturando(false);
      setConfirmFacturarOpen(false);
    }
  };

  const loadMotosListado = async () => {
    try {
      setLoading(true);
      const data = await tallerApi.getMotos({ search: searchMoto });
      const parsed = parseListado(data);
      setMotosListado(parsed.items);
    } catch (error) {
      console.error('Error al cargar motos:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMotoFormOptions = async () => {
    try {
      const [clientesResp, proveedoresResp, mecanicosResp] = await Promise.all([
        ventasApi.getClientes({ is_active: true }),
        inventarioApi.getProveedores({ is_active: true }),
        tallerApi.getMecanicos({ is_active: true }),
      ]);
      setClientes(parseListado(clientesResp).items);
      setProveedores(parseListado(proveedoresResp).items);
      setMecanicos(parseListado(mecanicosResp).items);
    } catch (error) {
      console.error('Error al cargar catálogos:', error);
    }
  };

  const resetClienteForm = () => {
    setClienteSearch('');
    setShowClienteForm(false);
    setClienteFormData(createDefaultClienteForm());
    setClienteFormError(null);
  };

  const openCreateMoto = async () => {
    setMotoFormMode('create');
    setMotoFormError(null);
    setMotoFormData(createDefaultMotoForm());
    resetClienteForm();
    setMotoModalOpen(true);
    await loadMotoFormOptions();
  };

  const openEditMoto = async (moto: Moto) => {
    setMotoFormMode('edit');
    setMotoFormError(null);
    setMotoFormData({
      id: moto.id,
      placa: moto.placa,
      marca: moto.marca,
      modelo: moto.modelo ?? '',
      color: moto.color ?? '',
      anio: moto.anio ? String(moto.anio) : '',
      cliente: moto.cliente ? String(moto.cliente) : '',
      mecanico: moto.mecanico ? String(moto.mecanico) : '',
      proveedor: moto.proveedor ? String(moto.proveedor) : '',
      observaciones: moto.observaciones ?? '',
      is_active: moto.is_active,
    });
    resetClienteForm();
    setMotoModalOpen(true);
    await loadMotoFormOptions();
  };

  const closeMotoModal = () => {
    if (savingMoto) return;
    setMotoModalOpen(false);
    setMotoFormData(createDefaultMotoForm());
    setMotoFormError(null);
    resetClienteForm();
  };

  const handleCreateCliente = async () => {
    if (!clienteFormData.numero_documento.trim() || !clienteFormData.nombre.trim()) {
      setClienteFormError('Completa el documento y el nombre del cliente.');
      return;
    }
    try {
      setSavingCliente(true);
      setClienteFormError(null);
      const nuevoCliente = await ventasApi.crearCliente(clienteFormData);
      setClientes((prev) => [...prev, nuevoCliente]);
      setMotoFormData((prev) => ({ ...prev, cliente: String(nuevoCliente.id) }));
      setClienteSearch(nuevoCliente.nombre);
      setShowClienteForm(false);
      setClienteFormData(createDefaultClienteForm());
      showNotification({
        message: 'Cliente registrado correctamente.',
        type: 'success',
      });
    } catch (error: any) {
      console.error('Error al registrar cliente:', error);
      setClienteFormError('No se pudo registrar el cliente.');
    } finally {
      setSavingCliente(false);
    }
  };

  const handleMotoSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSavingMoto(true);
    setMotoFormError(null);

    const payload: Partial<Moto> = {
      placa: motoFormData.placa,
      marca: motoFormData.marca,
      modelo: motoFormData.modelo,
      color: motoFormData.color,
      anio: motoFormData.anio ? Number(motoFormData.anio) : null,
      cliente: motoFormData.cliente ? Number(motoFormData.cliente) : null,
      mecanico: motoFormData.mecanico ? Number(motoFormData.mecanico) : null,
      proveedor: motoFormData.proveedor ? Number(motoFormData.proveedor) : null,
      observaciones: motoFormData.observaciones,
      is_active: motoFormData.is_active,
    };

    try {
      if (motoFormMode === 'create') {
        await tallerApi.createMoto(payload);
      } else if (motoFormData.id) {
        await tallerApi.updateMoto(motoFormData.id, payload);
      }
      closeMotoModal();
      await loadMotosListado();
      showNotification({
        message:
          motoFormMode === 'create'
            ? 'Moto creada correctamente.'
            : 'Moto actualizada correctamente.',
        type: 'success',
      });
    } catch (error: any) {
      console.error('Error al guardar moto:', error);
      setMotoFormError('No se pudo guardar la información.');
    } finally {
      setSavingMoto(false);
    }
  };

  const handleMotoDelete = async () => {
    if (!selectedMotoListId) {
      showNotification({
        message: 'Selecciona una moto para eliminar.',
        type: 'error',
      });
      return;
    }
    setConfirmDeleteOpen(true);
  };

  const confirmMotoDelete = async () => {
    if (!selectedMotoListId) return;
    try {
      setLoading(true);
      await tallerApi.deleteMoto(selectedMotoListId);
      setSelectedMotoListId(null);
      await loadMotosListado();
      showNotification({
        message: 'Moto eliminada correctamente.',
        type: 'success',
      });
    } catch (error) {
      console.error('Error al eliminar moto:', error);
      showNotification({
        message: 'No se pudo eliminar la moto.',
        type: 'error',
      });
    } finally {
      setLoading(false);
      setConfirmDeleteOpen(false);
    }
  };

  const totalOrden = useMemo(() => {
    if (!ordenActual) return 0;
    return Number(ordenActual.total || 0);
  }, [ordenActual]);

  const filteredClientes = useMemo(() => {
    const term = clienteSearch.trim().toLowerCase();
    if (!term) return clientes;
    return clientes.filter((cliente) => {
      const nombre = cliente.nombre?.toLowerCase() ?? '';
      const documento = cliente.numero_documento?.toLowerCase() ?? '';
      return nombre.includes(term) || documento.includes(term);
    });
  }, [clienteSearch, clientes]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase text-blue-500">Taller</p>
            <h1 className="text-xl font-semibold text-slate-900">{activeTabConfig.label}</h1>
            <p className="text-sm text-slate-500">{activeTabConfig.description}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => (activeTab === 'ordenes' ? loadMecanicos() : loadMotosListado())}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-blue-200 hover:text-blue-600"
            >
              <RefreshCw size={16} />
              Actualizar
            </button>
            {activeTab === 'motos' && (
              <button
                type="button"
                onClick={openCreateMoto}
                className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
              >
                <Plus size={16} />
                Nueva moto
              </button>
            )}
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

        {activeTab === 'ordenes' ? (
          <div className="space-y-4 px-4 py-4">
            <div className="grid gap-4 xl:grid-cols-[260px_1fr]">
              <section className="space-y-4">
                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2">
                    <div>
                      <h2 className="text-xs font-semibold uppercase text-slate-600">
                        Seleccione mecánico
                      </h2>
                      <p className="text-[11px] text-slate-500">Lista de técnicos disponibles</p>
                    </div>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm">
                      {mecanicos.length}
                    </span>
                  </div>
                  <div className="px-3 py-3">
                    {mecanicos.length === 0 ? (
                      <div className="border border-dashed border-slate-200 px-3 py-4 text-center text-xs text-slate-500">
                        No hay mecánicos.
                      </div>
                    ) : (
                      <label className="flex flex-col gap-2 text-xs font-semibold text-slate-700">
                        Mecánico en turno
                        <select
                          value={selectedMecanicoId ?? ''}
                          onChange={(event) => {
                            const value = event.target.value;
                            setSelectedMecanicoId(value ? Number(value) : null);
                          }}
                          className="rounded-md border border-slate-200 px-2 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                        >
                          <option value="" disabled>
                            Selecciona un mecánico
                          </option>
                          {mecanicos.map((mecanico) => (
                            <option key={mecanico.id} value={mecanico.id}>
                              {mecanico.nombre}
                            </option>
                          ))}
                        </select>
                        {selectedMecanicoId && (
                          <div className="border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-500">
                            {mecanicos.find((mecanico) => mecanico.id === selectedMecanicoId)?.telefono ||
                              'Sin teléfono'}
                          </div>
                        )}
                      </label>
                    )}
                  </div>
                </div>

                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-2">
                    <div>
                      <h2 className="text-xs font-semibold uppercase text-slate-600">Motos asociadas</h2>
                      <p className="text-[11px] text-slate-500">Doble clic para abrir la orden</p>
                    </div>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-600 shadow-sm">
                      {motosPorMecanico.length}
                    </span>
                  </div>
                  <div className="max-h-[360px] overflow-y-auto">
                    {motosPorMecanico.length === 0 ? (
                      <div className="p-3 text-center text-xs text-slate-500">
                        No hay motos asignadas.
                      </div>
                    ) : (
                      <table className="w-full text-xs">
                        <thead className="bg-slate-100 text-left text-[11px] font-semibold uppercase text-slate-500">
                          <tr>
                            <th className="px-3 py-2">Placa</th>
                            <th className="px-3 py-2">Marca</th>
                            <th className="px-3 py-2">Modelo</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {motosPorMecanico.map((moto) => (
                            <tr
                              key={moto.id}
                              className={`cursor-pointer transition ${
                                selectedMotoId === moto.id ? 'bg-blue-100' : 'hover:bg-slate-50'
                              }`}
                              onClick={() => handleSelectMoto(moto)}
                              onDoubleClick={() => handleSelectMoto(moto)}
                            >
                              <td className="px-3 py-2 font-semibold text-slate-800">{moto.placa}</td>
                              <td className="px-3 py-2">{moto.marca}</td>
                              <td className="px-3 py-2">{moto.modelo || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>

                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-200 bg-slate-50 px-3 py-2">
                    <h2 className="text-xs font-semibold uppercase text-slate-600">Registro de motos</h2>
                    <p className="text-[11px] text-slate-500">Crear o editar motos del taller</p>
                  </div>
                  <div className="flex flex-wrap gap-2 px-3 py-3">
                    <button
                      type="button"
                      onClick={openCreateMoto}
                      className="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] font-semibold text-blue-700 transition hover:bg-blue-100"
                    >
                      <Plus size={14} />
                      Registrar
                    </button>
                    <button
                      type="button"
                      onClick={handleEditMotoSeleccionada}
                      className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-600"
                    >
                      <Pencil size={14} />
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={() => setSearchParams({ tab: 'motos' })}
                      className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-600"
                    >
                      <Bike size={14} />
                      Ver listado
                    </button>
                  </div>
                </div>
              </section>

              <section className="space-y-4">
                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-200 bg-slate-50 px-3 py-2">
                    <h2 className="text-xs font-semibold uppercase text-slate-600">
                      Escriba el código y presione buscar
                    </h2>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 px-3 py-3">
                    <div className="flex flex-1 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
                      <Search size={14} className="text-slate-400" />
                      <input
                        type="text"
                        value={searchRepuesto}
                        onChange={(event) => setSearchRepuesto(event.target.value)}
                        placeholder="Ej. Banda freno, 770..."
                        className="flex-1 bg-transparent text-xs text-slate-700 outline-none"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        handleBuscarRepuestos();
                        setRepuestoModalOpen(true);
                      }}
                      className="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] font-semibold text-blue-700 transition hover:bg-blue-100"
                    >
                      <Search size={14} />
                      Buscar
                    </button>
                    <button
                      type="button"
                      onClick={handleFacturar}
                      disabled={facturando || !ordenActual || ordenActual.repuestos.length === 0}
                      className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-[11px] font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <PackageCheck size={14} />
                      {facturando ? 'Enviando...' : 'Facturar'}
                    </button>
                    <button
                      type="button"
                      onClick={handleFacturar}
                      disabled={facturando || !ordenActual || ordenActual.repuestos.length === 0}
                      className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-[11px] font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <PackageCheck size={14} />
                      {facturando ? 'Enviando...' : 'Facturar'}
                    </button>
                  </div>
                  <div className="border-t border-slate-200 px-3 py-2 text-[11px] text-slate-500">
                    {repuestos.length > 0
                      ? `${repuestos.length} repuestos encontrados`
                      : 'Busca repuestos en el catálogo'}
                  </div>
                  <div className="border-t border-slate-200 px-3 py-2 text-[11px] text-slate-500">
                    {repuestos.length > 0
                      ? `${repuestos.length} repuestos encontrados`
                      : 'Busca repuestos en el catálogo'}
                  </div>
                  <div className="border-t border-slate-200 px-3 py-2 text-[11px] text-slate-500">
                    {repuestos.length > 0
                      ? `${repuestos.length} repuestos encontrados`
                      : 'Busca repuestos en el catálogo'}
                  </div>
                </div>

                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-200 bg-slate-50 px-3 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h2 className="text-xs font-semibold uppercase text-slate-600">Orden actual</h2>
                        <p className="text-[11px] text-slate-500">Repuestos asociados y total</p>
                      </div>
                      {ordenActual && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                          {ordenActual.estado.replace('_', ' ')}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="px-3 py-3">
                    {!ordenActual ? (
                      <div className="border border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">
                        Selecciona una moto para iniciar la orden.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
                          <div>
                            <span className="text-[11px] uppercase text-slate-400">
                              Orden #{ordenActual.id}
                            </span>
                            <div className="font-semibold text-slate-800">
                              {ordenActual.moto_placa} · {ordenActual.moto_marca}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {ordenActual.mecanico_nombre}
                            </div>
                          </div>
                        </div>
                        {ordenActual.repuestos.length === 0 ? (
                          <div className="border border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">
                            Aún no hay repuestos agregados.
                          </div>
                        ) : (
                          <div className="max-h-[260px] overflow-y-auto border border-slate-200">
                            <table className="w-full text-xs">
                              <thead className="bg-slate-100 text-left text-[11px] font-semibold uppercase text-slate-500">
                                <tr>
                                  <th className="px-3 py-2">Artículo</th>
                                  <th className="px-3 py-2">Cantidad</th>
                                  <th className="px-3 py-2">Subtotal</th>
                                  <th className="px-3 py-2"></th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {ordenActual.repuestos.map((repuesto) => (
                                  <tr key={repuesto.id}>
                                    <td className="px-3 py-2">{repuesto.producto_nombre}</td>
                                    <td className="px-3 py-2">{repuesto.cantidad}</td>
                                    <td className="px-3 py-2">
                                      ${Number(repuesto.subtotal).toLocaleString()}
                                    </td>
                                    <td className="px-3 py-2 text-right">
                                      <button
                                        type="button"
                                        onClick={() => handleQuitarRepuesto(repuesto.id)}
                                        className="inline-flex items-center gap-1 rounded-md border border-rose-200 px-2 py-1 text-[11px] font-semibold text-rose-600 transition hover:bg-rose-50"
                                      >
                                        <Trash2 size={12} />
                                        Quitar
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-2 text-xs font-semibold text-slate-700">
                          <span>
                            Moto:{' '}
                            {ordenActual.moto_placa
                              ? `${ordenActual.moto_placa} · ${ordenActual.moto_marca}`
                              : 'Sin seleccionar'}
                          </span>
                          <span>Total cuentas: ${totalOrden.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-end pt-3">
                          <button
                            type="button"
                            onClick={handleFacturar}
                            disabled={facturando || ordenActual.repuestos.length === 0}
                            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-[11px] font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <PackageCheck size={14} />
                            {facturando ? 'Enviando...' : 'Facturar'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </div>
          </div>
        ) : (
          <div className="space-y-4 px-6 py-6">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={openCreateMoto}
                className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-100"
              >
                <Plus size={14} />
                Registrar
              </button>
                  <button
                    type="button"
                    onClick={() => {
                      const selected = motosListado.find((moto) => moto.id === selectedMotoListId);
                      if (!selected) {
                        showNotification({
                          message: 'Selecciona una moto para editar.',
                          type: 'error',
                        });
                        return;
                      }
                      openEditMoto(selected);
                    }}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-600"
              >
                <Pencil size={14} />
                Editar
              </button>
              <button
                type="button"
                onClick={handleMotoDelete}
                className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-600 transition hover:bg-rose-100"
              >
                <Trash2 size={14} />
                Eliminar
              </button>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-1 items-center gap-3 rounded-full border border-slate-200 bg-white px-4 py-2 shadow-sm">
                <Search size={16} className="text-slate-400" />
                <input
                  type="text"
                  value={searchMoto}
                  onChange={(event) => setSearchMoto(event.target.value)}
                  placeholder="Buscar por placa, marca o cliente..."
                  className="flex-1 bg-transparent text-sm text-slate-700 outline-none"
                />
              </div>
              <span className="text-xs text-slate-400">Doble clic para editar</span>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
              {loading ? (
                <div className="p-8 text-center text-sm text-slate-500">Cargando información...</div>
              ) : motosListado.length === 0 ? (
                <div className="p-8 text-center text-sm text-slate-500">No hay motos registradas.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-slate-100 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Placa</th>
                      <th className="px-4 py-3">Marca</th>
                      <th className="px-4 py-3">Modelo</th>
                      <th className="px-4 py-3">Mecánico</th>
                      <th className="px-4 py-3">Proveedor</th>
                      <th className="px-4 py-3">Cliente</th>
                      <th className="px-4 py-3">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {motosListado.map((moto) => (
                      <tr
                        key={moto.id}
                        className={`cursor-pointer transition ${
                          selectedMotoListId === moto.id ? 'bg-blue-100' : 'hover:bg-slate-50'
                        }`}
                        onClick={() => setSelectedMotoListId(moto.id)}
                        onDoubleClick={() => openEditMoto(moto)}
                      >
                        <td className="px-4 py-3 font-medium text-slate-800">{moto.placa}</td>
                        <td className="px-4 py-3">{moto.marca}</td>
                        <td className="px-4 py-3">{moto.modelo || '—'}</td>
                        <td className="px-4 py-3">{moto.mecanico_nombre || '—'}</td>
                        <td className="px-4 py-3">{moto.proveedor_nombre || '—'}</td>
                        <td className="px-4 py-3">{moto.cliente_nombre || '—'}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-1 text-xs font-semibold ${
                              moto.is_active
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {moto.is_active ? 'Activa' : 'Inactiva'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>

      {motoModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
          <div className="w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-blue-500">
                  {motoFormMode === 'create' ? 'Nueva moto' : 'Editar moto'}
                </p>
                <h2 className="text-lg font-semibold text-slate-900">
                  {motoFormMode === 'create'
                    ? 'Registrar información'
                    : 'Actualizar información'}
                </h2>
              </div>
              <button
                type="button"
                onClick={closeMotoModal}
                className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleMotoSubmit} className="space-y-6 px-6 py-4">
              {motoFormError && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
                  {motoFormError}
                </div>
              )}
              <div className="grid gap-4 md:grid-cols-2">
                <InputField
                  label="Placa"
                  name="placa"
                  value={motoFormData.placa}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, placa: value }))}
                  required
                />
                <InputField
                  label="Marca"
                  name="marca"
                  value={motoFormData.marca}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, marca: value }))}
                  required
                />
                <InputField
                  label="Modelo"
                  name="modelo"
                  value={motoFormData.modelo}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, modelo: value }))}
                />
                <InputField
                  label="Color"
                  name="color"
                  value={motoFormData.color}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, color: value }))}
                />
                <InputField
                  label="Año"
                  name="anio"
                  type="number"
                  value={motoFormData.anio}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, anio: value }))}
                />
                <div className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                  <span>Cliente</span>
                  <div className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-100">
                    <Search size={16} className="text-slate-400" />
                    <input
                      type="text"
                      value={clienteSearch}
                      onChange={(event) => setClienteSearch(event.target.value)}
                      placeholder="Buscar por nombre o documento"
                      className="flex-1 bg-transparent text-sm text-slate-700 outline-none"
                    />
                  </div>
                  <select
                    name="cliente"
                    value={motoFormData.cliente}
                    onChange={(event) =>
                      setMotoFormData((prev) => ({ ...prev, cliente: event.target.value }))
                    }
                    className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                  >
                    <option value="">Seleccionar cliente</option>
                    {filteredClientes.length === 0 ? (
                      <option value="" disabled>
                        Sin coincidencias
                      </option>
                    ) : (
                      filteredClientes.map((cliente) => (
                        <option key={cliente.id} value={String(cliente.id)}>
                          {cliente.nombre} ({cliente.numero_documento})
                        </option>
                      ))
                    )}
                  </select>
                  <button
                    type="button"
                    onClick={() => {
                      setShowClienteForm((prev) => !prev);
                      setClienteFormError(null);
                    }}
                    className="self-start text-xs font-semibold text-blue-600 transition hover:text-blue-700"
                  >
                    {showClienteForm ? 'Cancelar registro de cliente' : 'Registrar cliente nuevo'}
                  </button>
                </div>
                <SelectField
                  label="Mecánico"
                  name="mecanico"
                  value={motoFormData.mecanico}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, mecanico: value }))}
                  options={mecanicos.map((mecanico) => ({
                    value: String(mecanico.id),
                    label: mecanico.nombre,
                  }))}
                  placeholder="Seleccionar mecánico"
                />
                <SelectField
                  label="Proveedor (opcional)"
                  name="proveedor"
                  value={motoFormData.proveedor}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, proveedor: value }))}
                  options={proveedores.map((proveedor) => ({
                    value: String(proveedor.id),
                    label: proveedor.nombre,
                  }))}
                  placeholder="Seleccionar proveedor (opcional)"
                />
                {showClienteForm && (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 md:col-span-2">
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <p className="text-xs font-semibold uppercase text-blue-500">
                          Nuevo cliente
                        </p>
                        <p className="text-sm text-slate-600">
                          Registra el cliente sin salir del formulario.
                        </p>
                      </div>
                    </div>
                    {clienteFormError && (
                      <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600">
                        {clienteFormError}
                      </div>
                    )}
                    <div className="grid gap-4 md:grid-cols-2">
                      <SelectField
                        label="Tipo de documento"
                        name="tipo_documento"
                        value={clienteFormData.tipo_documento}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({
                            ...prev,
                            tipo_documento: value as Cliente['tipo_documento'],
                          }))
                        }
                        options={documentoOptions}
                      />
                      <InputField
                        label="Número de documento"
                        name="numero_documento"
                        value={clienteFormData.numero_documento}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({ ...prev, numero_documento: value }))
                        }
                      />
                      <InputField
                        label="Nombre / Razón social"
                        name="nombre"
                        value={clienteFormData.nombre}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({ ...prev, nombre: value }))
                        }
                      />
                      <InputField
                        label="Teléfono"
                        name="telefono"
                        value={clienteFormData.telefono}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({ ...prev, telefono: value }))
                        }
                      />
                      <InputField
                        label="Email"
                        name="email"
                        type="email"
                        value={clienteFormData.email}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({ ...prev, email: value }))
                        }
                      />
                      <InputField
                        label="Ciudad"
                        name="ciudad"
                        value={clienteFormData.ciudad}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({ ...prev, ciudad: value }))
                        }
                      />
                      <TextAreaField
                        label="Dirección"
                        name="direccion"
                        value={clienteFormData.direccion}
                        onChange={(value) =>
                          setClienteFormData((prev) => ({ ...prev, direccion: value }))
                        }
                      />
                      <CheckboxField
                        label="Cliente activo"
                        name="is_active"
                        checked={clienteFormData.is_active}
                        onChange={(checked) =>
                          setClienteFormData((prev) => ({ ...prev, is_active: checked }))
                        }
                      />
                    </div>
                    <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setShowClienteForm(false);
                          setClienteFormError(null);
                        }}
                        className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 transition hover:border-slate-300"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={handleCreateCliente}
                        disabled={savingCliente}
                        className="rounded-full bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        {savingCliente ? 'Guardando...' : 'Guardar cliente'}
                      </button>
                    </div>
                  </div>
                )}
                <TextAreaField
                  label="Observaciones"
                  name="observaciones"
                  value={motoFormData.observaciones}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, observaciones: value }))}
                />
                <CheckboxField
                  label="Moto activa"
                  name="is_active"
                  checked={motoFormData.is_active}
                  onChange={(checked) => setMotoFormData((prev) => ({ ...prev, is_active: checked }))}
                />
              </div>
              <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={closeMotoModal}
                  className="rounded-full border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:border-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={savingMoto}
                  className="rounded-full bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {savingMoto ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      <ConfirmModal
        open={confirmFacturarOpen}
        title="Enviar a facturación"
        description="La orden será enviada a facturación. ¿Deseas continuar?"
        confirmLabel="Enviar"
        confirmVariant="primary"
        onConfirm={confirmFacturar}
        onCancel={() => setConfirmFacturarOpen(false)}
        loading={facturando}
      />
      <ConfirmModal
        open={confirmDeleteOpen}
        title="Eliminar moto"
        description="Esta acción eliminará la moto seleccionada. ¿Deseas continuar?"
        confirmLabel="Eliminar"
        confirmVariant="danger"
        onConfirm={confirmMotoDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
        loading={loading}
      />
      {repuestoModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
          <div className="w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-blue-500">Repuestos</p>
                <h2 className="text-lg font-semibold text-slate-900">Buscar repuestos</h2>
              </div>
              <button
                type="button"
                onClick={closeRepuestoModal}
                className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-4 px-6 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex flex-1 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 shadow-sm">
                  <Search size={16} className="text-slate-400" />
                  <input
                    type="text"
                    value={searchRepuesto}
                    onChange={(event) => setSearchRepuesto(event.target.value)}
                    placeholder="Ej. Banda freno, 770..."
                    className="flex-1 bg-transparent text-sm text-slate-700 outline-none"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleBuscarRepuestos}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-600"
                >
                  <Search size={14} />
                  Buscar
                </button>
              </div>
              <div className="max-h-[360px] overflow-y-auto rounded-xl border border-slate-200">
                {repuestos.length === 0 ? (
                  <div className="p-6 text-center text-sm text-slate-500">
                    {searchRepuesto ? 'No hay resultados.' : 'Empieza a buscar repuestos.'}
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                      <tr>
                        <th className="px-3 py-2">Código</th>
                        <th className="px-3 py-2">Artículo</th>
                        <th className="px-3 py-2">Stock</th>
                        <th className="px-3 py-2">Cantidad</th>
                        <th className="px-3 py-2"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {repuestos.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-50">
                          <td className="px-3 py-2 font-medium text-slate-800">{item.codigo}</td>
                          <td className="px-3 py-2">{item.nombre}</td>
                          <td className="px-3 py-2">{item.stock}</td>
                          <td className="px-3 py-2">
                            <input
                              type="number"
                              min={1}
                              value={cantidades[item.id] ?? 1}
                              onChange={(event) =>
                                setCantidades((prev) => ({
                                  ...prev,
                                  [item.id]: Number(event.target.value) || 1,
                                }))
                              }
                              className="w-20 rounded-md border border-slate-200 px-2 py-1 text-xs"
                            />
                          </td>
                          <td className="px-3 py-2 text-right">
                            <button
                              type="button"
                              onClick={() => handleAgregarRepuesto(item.id)}
                              className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-blue-700"
                            >
                              <Plus size={14} />
                              Agregar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const InputField = ({
  label,
  name,
  value,
  onChange,
  type = 'text',
  required,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) => (
  <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
    {label}
    <input
      type={type}
      name={name}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required={required}
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
}: {
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
}) => (
  <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
    {label}
    <select
      name={name}
      value={value}
      onChange={(event) => onChange(event.target.value)}
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
  value: string;
  onChange: (value: string) => void;
}) => (
  <label className="flex flex-col gap-2 text-sm font-medium text-slate-700 md:col-span-2">
    {label}
    <textarea
      name={name}
      value={value}
      onChange={(event) => onChange(event.target.value)}
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
  onChange: (value: boolean) => void;
}) => (
  <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
    <input
      type="checkbox"
      name={name}
      checked={checked}
      onChange={(event) => onChange(event.target.checked)}
      className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-200"
    />
    {label}
  </label>
);
