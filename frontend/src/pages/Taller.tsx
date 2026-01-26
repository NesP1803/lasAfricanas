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
  BadgeCheck,
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
      setOrdenActual(orden);
      setCantidades((prev) => ({ ...prev, [productoId]: 1 }));
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

  const handleQuitarRepuesto = async (repuestoId: number) => {
    if (!ordenActual) return;
    try {
      const orden = await tallerApi.quitarRepuesto(ordenActual.id, { repuesto_id: repuestoId });
      setOrdenActual(orden);
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

  const openCreateMoto = async () => {
    setMotoFormMode('create');
    setMotoFormError(null);
    setMotoFormData(createDefaultMotoForm());
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
    setMotoModalOpen(true);
    await loadMotoFormOptions();
  };

  const closeMotoModal = () => {
    if (savingMoto) return;
    setMotoModalOpen(false);
    setMotoFormData(createDefaultMotoForm());
    setMotoFormError(null);
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
          <div className="space-y-6 px-6 py-6">
            <div className="grid gap-6 xl:grid-cols-3">
              <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-800">Mecánicos</h2>
                    <p className="text-xs text-slate-500">Selecciona el mecánico en turno</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                    {mecanicos.length}
                  </span>
                </div>
                <div className="max-h-[420px] overflow-y-auto">
                  {mecanicos.length === 0 ? (
                    <div className="p-4 text-center text-sm text-slate-500">No hay mecánicos.</div>
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {mecanicos.map((mecanico) => (
                        <li key={mecanico.id}>
                          <button
                            type="button"
                            onClick={() => setSelectedMecanicoId(mecanico.id)}
                            className={`flex w-full items-center justify-between px-4 py-3 text-left text-sm transition ${
                              selectedMecanicoId === mecanico.id
                                ? 'bg-blue-100 text-blue-700'
                                : 'hover:bg-slate-50'
                            }`}
                          >
                            <div>
                              <p className="font-semibold text-slate-800">{mecanico.nombre}</p>
                              <p className="text-xs text-slate-500">{mecanico.telefono || 'Sin teléfono'}</p>
                            </div>
                            {selectedMecanicoId === mecanico.id && (
                              <BadgeCheck size={18} className="text-blue-600" />
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-800">Motos asociadas</h2>
                    <p className="text-xs text-slate-500">Doble clic para abrir la orden</p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                    {motosPorMecanico.length}
                  </span>
                </div>
                <div className="max-h-[420px] overflow-y-auto">
                  {motosPorMecanico.length === 0 ? (
                    <div className="p-4 text-center text-sm text-slate-500">
                      No hay motos asignadas.
                    </div>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                        <tr>
                          <th className="px-4 py-2">Placa</th>
                          <th className="px-4 py-2">Marca</th>
                          <th className="px-4 py-2">Modelo</th>
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
                            <td className="px-4 py-3 font-semibold text-slate-800">{moto.placa}</td>
                            <td className="px-4 py-3">{moto.marca}</td>
                            <td className="px-4 py-3">{moto.modelo || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>

              <section className="space-y-6">
                <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-200 px-4 py-3">
                    <h2 className="text-sm font-semibold text-slate-800">Buscar repuestos</h2>
                    <p className="text-xs text-slate-500">Busca por código o nombre del artículo</p>
                  </div>
                  <div className="px-4 py-4">
                    <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 shadow-sm">
                      <Search size={16} className="text-slate-400" />
                      <input
                        type="text"
                        value={searchRepuesto}
                        onChange={(event) => setSearchRepuesto(event.target.value)}
                        placeholder="Ej. Banda freno, 770..."
                        className="flex-1 bg-transparent text-sm text-slate-700 outline-none"
                      />
                    </div>
                  </div>
                  <div className="max-h-[240px] overflow-y-auto">
                    {repuestos.length === 0 ? (
                      <div className="p-4 text-center text-xs text-slate-500">
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

                <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-200 px-4 py-3">
                    <h2 className="text-sm font-semibold text-slate-800">Orden actual</h2>
                    <p className="text-xs text-slate-500">Repuestos asociados y total</p>
                  </div>
                  <div className="px-4 py-4">
                    {!ordenActual ? (
                      <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">
                        Selecciona una moto para iniciar la orden.
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-xs uppercase text-slate-400">Orden #{ordenActual.id}</p>
                            <h3 className="text-sm font-semibold text-slate-800">
                              {ordenActual.moto_placa} · {ordenActual.moto_marca}
                            </h3>
                            <p className="text-xs text-slate-500">{ordenActual.mecanico_nombre}</p>
                          </div>
                          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                            {ordenActual.estado.replace('_', ' ')}
                          </span>
                        </div>
                        {ordenActual.repuestos.length === 0 ? (
                          <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-xs text-slate-500">
                            Aún no hay repuestos agregados.
                          </div>
                        ) : (
                          <div className="max-h-[200px] overflow-y-auto">
                            <table className="w-full text-sm">
                              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
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
                                    <td className="px-3 py-2">${Number(repuesto.subtotal).toLocaleString()}</td>
                                    <td className="px-3 py-2 text-right">
                                      <button
                                        type="button"
                                        onClick={() => handleQuitarRepuesto(repuesto.id)}
                                        className="inline-flex items-center gap-1 rounded-full border border-rose-200 px-2 py-1 text-xs font-semibold text-rose-600 transition hover:bg-rose-50"
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
                        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-3">
                          <div className="text-sm font-semibold text-slate-700">
                            Total: ${totalOrden.toLocaleString()}
                          </div>
                          <button
                            type="button"
                            onClick={handleFacturar}
                            disabled={facturando || ordenActual.repuestos.length === 0}
                            className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <PackageCheck size={14} />
                            {facturando ? 'Enviando...' : 'Enviar a facturar'}
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
                <SelectField
                  label="Cliente"
                  name="cliente"
                  value={motoFormData.cliente}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, cliente: value }))}
                  options={clientes.map((cliente) => ({
                    value: String(cliente.id),
                    label: `${cliente.nombre} (${cliente.numero_documento})`,
                  }))}
                  placeholder="Seleccionar cliente"
                />
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
                  label="Proveedor"
                  name="proveedor"
                  value={motoFormData.proveedor}
                  onChange={(value) => setMotoFormData((prev) => ({ ...prev, proveedor: value }))}
                  options={proveedores.map((proveedor) => ({
                    value: String(proveedor.id),
                    label: proveedor.nombre,
                  }))}
                  placeholder="Seleccionar proveedor"
                />
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
