import { useEffect, useMemo, useState } from 'react';
import { Eye, Plus, RefreshCw, Save, Trash2 } from 'lucide-react';
import {
  configuracionAPI,
  type FacturacionRango,
  type FactusHealthResponse,
} from '../../../api/configuracion';
import type { ConfiguracionFacturacion } from '../../../types';

type TabKey = 'resumen' | 'rangos' | 'consecutivos' | 'remisiones';
type CreateTab = 'autorizado' | 'manual';

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'resumen', label: 'Resumen' },
  { key: 'rangos', label: 'Rangos de numeración' },
  { key: 'consecutivos', label: 'Consecutivos' },
  { key: 'remisiones', label: 'Remisiones' },
];

const DOC_OPTIONS = [
  { value: 'FACTURA_VENTA', label: 'Factura de venta', factusDocument: '21' },
  { value: 'NOTA_CREDITO', label: 'Nota crédito', factusDocument: '22' },
  { value: 'DOCUMENTO_SOPORTE', label: 'Documento soporte', factusDocument: '24' },
] as const;

const STATUS_OPTIONS = [
  { value: 'todos', label: 'Todos' },
  { value: 'activo', label: 'Activo' },
  { value: 'inactivo', label: 'Inactivo' },
  { value: 'vencido', label: 'Vencido' },
  { value: 'seleccionado', label: 'Seleccionado' },
] as const;

type RemisionNumeracionPayload = {
  prefix?: string;
  current?: number;
  range_from?: number;
  range_to?: number;
  resolution_reference?: string;
  notes?: string;
};

type RangoForm = {
  document_code: string;
  prefijo: string;
  desde: number;
  hasta: number;
  consecutivo_actual: number;
  resolucion: string;
  fecha_autorizacion: string;
  fecha_expiracion: string;
  technical_key: string;
  factus_id?: number | null;
  factus_range_id?: number | null;
};

const emptyForm: RangoForm = {
  document_code: 'FACTURA_VENTA',
  prefijo: '',
  desde: 1,
  hasta: 1,
  consecutivo_actual: 1,
  resolucion: '',
  fecha_autorizacion: '',
  fecha_expiracion: '',
  technical_key: '',
  factus_id: null,
  factus_range_id: null,
};

const getApiErrorMessage = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object' || !('response' in error)) return undefined;
  const response = (error as { response?: { data?: { detail?: string } } }).response;
  return response?.data?.detail;
};

type Props = {
  isAdmin: boolean;
  facturacion: ConfiguracionFacturacion;
  onFacturacionChange: (next: ConfiguracionFacturacion) => void;
  onSaveFacturacion: () => Promise<void>;
};

export default function FacturacionElectronicaAdmin({
  isAdmin,
  facturacion,
  onFacturacionChange,
  onSaveFacturacion,
}: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>('resumen');
  const [rangos, setRangos] = useState<FacturacionRango[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [degradedWarning, setDegradedWarning] = useState('');
  const [factusHealth, setFactusHealth] = useState<FactusHealthResponse | null>(null);
  const [remision, setRemision] = useState<RemisionNumeracionPayload>({});
  const [detalleRango, setDetalleRango] = useState<unknown>(null);

  const [docFilter, setDocFilter] = useState<string>('');
  const [stateFilter, setStateFilter] = useState<string>('todos');

  const [showModal, setShowModal] = useState(false);
  const [createTab, setCreateTab] = useState<CreateTab>('autorizado');
  const [form, setForm] = useState<RangoForm>(emptyForm);
  const [activateNow, setActivateNow] = useState(true);
  const [availableRanges, setAvailableRanges] = useState<Record<string, unknown>[]>([]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    setDegradedWarning('');

    const query = {
      document_code: docFilter || undefined,
      estado: stateFilter !== 'todos' ? stateFilter : undefined,
    };

    const [rangosRes, softwareRes, remisionRes, healthRes] = await Promise.allSettled([
      configuracionAPI.listarRangosFacturacion(query),
      configuracionAPI.obtenerRangosSoftware(),
      configuracionAPI.obtenerNumeracionRemision(),
      configuracionAPI.obtenerFactusHealth(),
    ]);

    if (rangosRes.status === 'fulfilled') {
      setRangos(rangosRes.value);
    } else {
      setError(rangosRes.reason?.response?.data?.detail || 'No fue posible cargar los rangos.');
    }

    if (softwareRes.status === 'fulfilled') {
      if (softwareRes.value.status === 'degraded') {
        setDegradedWarning(softwareRes.value.detail || 'No fue posible consultar Factus en este momento.');
      }
    }

    if (remisionRes.status === 'fulfilled') setRemision(remisionRes.value || {});
    if (healthRes.status === 'fulfilled') setFactusHealth(healthRes.value);
    setLoading(false);
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docFilter, stateFilter]);

  const stats = useMemo(() => {
    const active = rangos.filter((r) => r.is_active_remote).length;
    const expired = rangos.filter((r) => r.is_expired_remote).length;
    return { active, expired };
  }, [rangos]);

  const applyRemoteRange = (remote: Record<string, unknown>) => {
    const startDate = String(remote.start_date || '').split('T')[0];
    const endDate = String(remote.end_date || '').split('T')[0];
    setForm((prev) => ({
      ...prev,
      prefijo: String(remote.prefix || ''),
      desde: Number(remote.from || 1),
      hasta: Number(remote.to || 1),
      consecutivo_actual: Number(remote.current || remote.from || 1),
      resolucion: String(remote.resolution_number || ''),
      fecha_autorizacion: startDate,
      fecha_expiracion: endDate,
      technical_key: String(remote.technical_key || ''),
      factus_id: Number(remote.id || remote.numbering_range_id || 0) || null,
      factus_range_id: Number(remote.id || remote.numbering_range_id || 0) || null,
    }));
    setAvailableRanges([]);
  };

  const handleBuscarRangosAutorizados = async () => {
    try {
      const selected = DOC_OPTIONS.find((d) => d.value === form.document_code);
      if (!selected) return;
      const software = await configuracionAPI.obtenerRangosSoftware();
      const remoteItems = software.items
        .map((row) => row.remote)
        .filter((item) => String(item.document || '') === selected.factusDocument);
      setAvailableRanges(remoteItems);
      if (!remoteItems.length) {
        setActionMessage('No hay rangos asociados al software para este documento.');
      }
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible consultar rangos asociados en Factus.');
    }
  };

  const handleCreate = async () => {
    setActionMessage('');
    try {
      await configuracionAPI.crearRangoFacturacion({
        ...form,
        is_active_remote: true,
        is_associated_to_software: createTab === 'autorizado',
        is_selected_local: activateNow,
        activo: true,
        activate_now: activateNow,
      });
      setActionMessage('Rango registrado correctamente.');
      setShowModal(false);
      setForm(emptyForm);
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible registrar el rango.');
    }
  };

  const toggleActivo = async (rango: FacturacionRango) => {
    try {
      await configuracionAPI.activarRangoFacturacion(rango.id, !rango.is_active_remote);
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible actualizar el estado del rango.');
    }
  };

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
      <div className="grid gap-3 md:grid-cols-5">
        <Stat title="Entorno" value={factusHealth?.environment || 'Desconocido'} />
        <Stat title="Token" value={factusHealth?.token_ok ? 'OK' : 'Pendiente'} />
        <Stat title="Rangos activos" value={stats.active} />
        <Stat title="Rangos vencidos" value={stats.expired} />
        <button type="button" onClick={loadData} className="inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold">
          <RefreshCw size={14} /> Recargar
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {tabs.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)} className={`rounded-lg px-3 py-1 text-xs font-semibold ${activeTab === tab.key ? 'bg-violet-600 text-white' : 'bg-slate-100 text-slate-700'}`}>
            {tab.label}
          </button>
        ))}
      </div>

      {error ? <p className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-600">{error}</p> : null}
      {degradedWarning ? <p className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-700">{degradedWarning}</p> : null}
      {actionMessage ? <p className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-sm text-blue-700">{actionMessage}</p> : null}
      {loading ? <p className="mt-3 text-sm text-slate-600">Cargando...</p> : null}

      {(activeTab === 'resumen' || activeTab === 'consecutivos') && (
        <div className="mt-4 rounded-lg border border-slate-200 p-3">
          <p className="mb-3 text-sm font-semibold text-slate-800">Numeración local del sistema</p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs font-semibold text-slate-600">Prefijo factura local
              <input className="mt-1 w-full rounded border px-2 py-1" value={facturacion.prefijo_factura} onChange={(e) => onFacturacionChange({ ...facturacion, prefijo_factura: e.target.value })} />
            </label>
            <label className="text-xs font-semibold text-slate-600">Consecutivo factura local
              <input className="mt-1 w-full rounded border px-2 py-1" type="number" value={facturacion.numero_factura} onChange={(e) => onFacturacionChange({ ...facturacion, numero_factura: Number(e.target.value) })} />
            </label>
          </div>
          <button type="button" onClick={onSaveFacturacion} className="mt-3 inline-flex items-center gap-2 rounded bg-violet-600 px-3 py-2 text-xs font-semibold text-white"><Save size={14} /> Guardar numeración local</button>
        </div>
      )}

      {activeTab === 'rangos' && (
        <div className="mt-4 rounded-lg border border-slate-200 p-3">
          <div className="mb-3 flex flex-wrap items-end gap-3">
            <label className="text-xs font-semibold">Tipo de documento
              <select className="mt-1 rounded border px-2 py-1" value={docFilter} onChange={(e) => setDocFilter(e.target.value)}>
                <option value="">Todos</option>
                {DOC_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="text-xs font-semibold">Estado
              <select className="mt-1 rounded border px-2 py-1" value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
                {STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <button type="button" className="ml-auto inline-flex items-center gap-2 rounded bg-violet-600 px-3 py-2 text-xs font-semibold text-white" onClick={() => setShowModal(true)} disabled={!isAdmin}><Plus size={14} /> Nuevo rango de numeración</button>
          </div>

          <div className="overflow-auto rounded border border-slate-200">
            <table className="min-w-full text-xs">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-2 py-2">Documento</th><th className="px-2 py-2">Prefijo</th><th className="px-2 py-2">Desde</th><th className="px-2 py-2">Hasta</th><th className="px-2 py-2">Actual</th><th className="px-2 py-2">Estado</th><th className="px-2 py-2">Vence en</th><th className="px-2 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {rangos.map((rango) => (
                  <tr key={rango.id} className="border-t border-slate-100">
                    <td className="px-2 py-2">{rango.document_code_label}</td>
                    <td className="px-2 py-2">{rango.prefijo}</td>
                    <td className="px-2 py-2">{rango.desde}</td>
                    <td className="px-2 py-2">{rango.hasta}</td>
                    <td className="px-2 py-2">{rango.consecutivo_actual}</td>
                    <td className="px-2 py-2">{rango.is_selected_local ? 'Seleccionado' : rango.is_expired_remote ? 'Vencido' : rango.is_active_remote ? 'Activo' : 'Inactivo'}</td>
                    <td className="px-2 py-2">{rango.fecha_expiracion || 'N/A'}</td>
                    <td className="px-2 py-2"><div className="flex flex-wrap gap-1">
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={async () => setDetalleRango(await configuracionAPI.obtenerDetalleRangoFacturacion(rango.id))}><Eye size={12} /></button>
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={() => configuracionAPI.seleccionarActivoRangoFacturacion(rango.id, rango.document_code).then(loadData)} disabled={!isAdmin}>Seleccionar</button>
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={() => toggleActivo(rango)} disabled={!isAdmin}>{rango.is_active_remote ? 'Desactivar' : 'Activar'}</button>
                      <button className="rounded bg-red-100 px-2 py-1 text-red-700" onClick={() => configuracionAPI.eliminarRangoFacturacion(rango.id).then(loadData)} disabled={!isAdmin}><Trash2 size={12} /></button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'remisiones' && (
        <div className="mt-4 rounded-lg border border-slate-200 p-3">
          <p className="mb-2 text-sm font-semibold">Numeración local de remisiones</p>
          <div className="grid gap-2 md:grid-cols-2">
            <input className="rounded border px-2 py-1" placeholder="Prefijo remisión" value={remision.prefix || ''} onChange={(e) => setRemision((prev) => ({ ...prev, prefix: e.target.value }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Consecutivo actual" value={remision.current || 1} onChange={(e) => setRemision((prev) => ({ ...prev, current: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Desde" value={remision.range_from || 1} onChange={(e) => setRemision((prev) => ({ ...prev, range_from: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Hasta" value={remision.range_to || 99999999} onChange={(e) => setRemision((prev) => ({ ...prev, range_to: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1 md:col-span-2" placeholder="Referencia interna" value={remision.resolution_reference || ''} onChange={(e) => setRemision((prev) => ({ ...prev, resolution_reference: e.target.value }))} />
            <textarea className="rounded border px-2 py-1 md:col-span-2" placeholder="Observaciones" value={remision.notes || ''} onChange={(e) => setRemision((prev) => ({ ...prev, notes: e.target.value }))} />
          </div>
          <button className="mt-3 inline-flex items-center gap-2 rounded bg-violet-600 px-3 py-2 text-xs font-semibold text-white" onClick={() => configuracionAPI.actualizarNumeracionRemision({ prefix: remision.prefix || 'REM', current: remision.current || 1, range_from: remision.range_from || 1, range_to: remision.range_to || 99999999, resolution_reference: remision.resolution_reference || '', notes: remision.notes || '' }).then(loadData)} disabled={!isAdmin}><Save size={14} /> Guardar</button>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-3">
          <div className="w-full max-w-4xl rounded-lg bg-white p-4">
            <h3 className="text-2xl font-semibold text-slate-700">Nuevo rango de numeración</h3>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button className={`rounded px-3 py-2 text-sm font-semibold ${createTab === 'autorizado' ? 'bg-violet-700 text-white' : 'bg-violet-300 text-white'}`} onClick={() => setCreateTab('autorizado')}>Rango autorizado</button>
              <button className={`rounded px-3 py-2 text-sm font-semibold ${createTab === 'manual' ? 'bg-violet-700 text-white' : 'bg-violet-300 text-white'}`} onClick={() => setCreateTab('manual')}>Rango manual</button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <label className="text-xs font-semibold">Documento
                <select className="mt-1 w-full rounded border px-2 py-2" value={form.document_code} onChange={(e) => setForm((prev) => ({ ...prev, document_code: e.target.value }))}>
                  {DOC_OPTIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
              </label>
              {createTab === 'autorizado' ? <div className="flex items-end"><button className="rounded bg-violet-600 px-3 py-2 text-sm font-semibold text-white" onClick={handleBuscarRangosAutorizados}>Buscar</button></div> : null}
              <Input label="Prefijo" value={form.prefijo} onChange={(v) => setForm((prev) => ({ ...prev, prefijo: v }))} />
              <Input label="Desde" type="number" value={String(form.desde)} onChange={(v) => setForm((prev) => ({ ...prev, desde: Number(v) }))} />
              <Input label="Hasta" type="number" value={String(form.hasta)} onChange={(v) => setForm((prev) => ({ ...prev, hasta: Number(v) }))} />
              <Input label="Número actual" type="number" value={String(form.consecutivo_actual)} onChange={(v) => setForm((prev) => ({ ...prev, consecutivo_actual: Number(v) }))} />
              <Input label="Número de resolución" value={form.resolucion} onChange={(v) => setForm((prev) => ({ ...prev, resolucion: v }))} />
              <Input label="Fecha de expedición" type="date" value={form.fecha_autorizacion} onChange={(v) => setForm((prev) => ({ ...prev, fecha_autorizacion: v }))} />
              <Input label="Fecha de vencimiento" type="date" value={form.fecha_expiracion} onChange={(v) => setForm((prev) => ({ ...prev, fecha_expiracion: v }))} />
              <div className="md:col-span-2"><Input label="Clave técnica" value={form.technical_key} onChange={(v) => setForm((prev) => ({ ...prev, technical_key: v }))} /></div>
              <label className="inline-flex items-center gap-2 text-sm font-medium md:col-span-2"><input type="checkbox" checked={activateNow} onChange={(e) => setActivateNow(e.target.checked)} /> Seleccionar como rango local activo al registrar</label>
            </div>
            {availableRanges.length > 0 && (
              <div className="mt-3 rounded border p-2">
                <p className="mb-2 text-sm font-semibold">Selecciona un rango de numeración</p>
                <div className="max-h-40 overflow-auto">
                  {availableRanges.map((item) => (
                    <button key={String(item.id || item.numbering_range_id)} className="block w-full rounded px-2 py-1 text-left hover:bg-slate-100" onClick={() => applyRemoteRange(item)}>
                      {String(item.prefix || '')} ({String(item.from || '')} - {String(item.to || '')})
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <button className="rounded border px-3 py-2 text-sm" onClick={() => setShowModal(false)}>Cerrar</button>
              <button className="rounded bg-violet-600 px-3 py-2 text-sm font-semibold text-white" onClick={handleCreate}>Registrar</button>
            </div>
          </div>
        </div>
      )}

      {detalleRango ? <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs"><div className="mb-2 flex items-center justify-between"><p className="font-semibold">Detalle rango</p><button className="rounded bg-white px-2 py-1" onClick={() => setDetalleRango(null)}>Cerrar</button></div><pre className="overflow-auto rounded bg-white p-2">{JSON.stringify(detalleRango, null, 2)}</pre></div> : null}
    </div>
  );
}

function Stat({ title, value }: { title: string; value: string | number }) {
  return <div className="rounded-lg border border-slate-200 bg-slate-50 p-2"><p className="text-xs text-slate-500">{title}</p><p className="text-sm font-semibold">{value}</p></div>;
}

function Input({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return <label className="text-xs font-semibold">{label}<input className="mt-1 w-full rounded border px-2 py-2" value={value} type={type} onChange={(e) => onChange(e.target.value)} /></label>;
}
