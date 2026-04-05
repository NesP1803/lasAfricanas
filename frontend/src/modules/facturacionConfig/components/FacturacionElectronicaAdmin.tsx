import { useEffect, useMemo, useState } from 'react';
import { Eye, RefreshCw, Save, Trash2 } from 'lucide-react';
import {
  configuracionAPI,
  type FacturacionRango,
  type SoftwareRangesResponse,
  type FactusHealthResponse,
} from '../../../api/configuracion';
import type { ConfiguracionFacturacion } from '../../../types';

type TabKey = 'resumen' | 'rangos' | 'consecutivos' | 'remisiones';

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'resumen', label: 'Resumen' },
  { key: 'rangos', label: 'Rangos Factus' },
  { key: 'consecutivos', label: 'Consecutivos' },
  { key: 'remisiones', label: 'Remisiones' },
];

type RemisionNumeracionPayload = {
  prefix?: string;
  current?: number;
  range_from?: number;
  range_to?: number;
  resolution_reference?: string;
  notes?: string;
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
  const [degradedWarning, setDegradedWarning] = useState('');
  const [factusHealth, setFactusHealth] = useState<FactusHealthResponse | null>(null);
  const [softwareRows, setSoftwareRows] = useState<SoftwareRangesResponse['items']>([]);
  const [remision, setRemision] = useState<RemisionNumeracionPayload>({});
  const [detalleRango, setDetalleRango] = useState<unknown>(null);
  const [actionMessage, setActionMessage] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError('');
    setDegradedWarning('');

    const [rangosRes, softwareRes, remisionRes, healthRes] = await Promise.allSettled([
      configuracionAPI.listarRangosFacturacion(),
      configuracionAPI.obtenerRangosSoftware(),
      configuracionAPI.obtenerNumeracionRemision(),
      configuracionAPI.obtenerFactusHealth(),
    ]);

    if (rangosRes.status === 'fulfilled') {
      setRangos(rangosRes.value);
    } else {
      setError(rangosRes.reason?.response?.data?.detail || 'No fue posible cargar los rangos de facturación.');
    }

    if (softwareRes.status === 'fulfilled') {
      setSoftwareRows(Array.isArray(softwareRes.value.items) ? softwareRes.value.items : []);
      if (softwareRes.value.status === 'degraded') {
        setDegradedWarning(
          softwareRes.value.detail ||
            'No fue posible consultar rangos asociados en Factus/DIAN. Se muestra estado degradado con datos locales.'
        );
      }
    } else {
      setDegradedWarning('No fue posible consultar rangos asociados en Factus/DIAN. Se muestra estado degradado con datos locales.');
      setSoftwareRows([]);
    }

    if (remisionRes.status === 'fulfilled') {
      setRemision(remisionRes.value || {});
    } else {
      setRemision({});
    }

    if (healthRes.status === 'fulfilled') {
      setFactusHealth(healthRes.value);
    } else {
      setFactusHealth(null);
    }

    setLoading(false);
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadData();
  }, []);

  const stats = useMemo(() => {
    const active = rangos.filter((r) => r.is_active_remote).length;
    const expired = rangos.filter((r) => r.is_expired_remote).length;
    const lastSync = rangos
      .map((r) => r.last_synced_at)
      .filter(Boolean)
      .sort()
      .at(-1);
    return { active, expired, lastSync };
  }, [rangos]);

  const handleSelect = async (rango: FacturacionRango) => {
    setActionMessage('');
    try {
      await configuracionAPI.seleccionarActivoRangoFacturacion(rango.id, rango.document_code);
      setActionMessage(`Rango ${rango.prefijo} seleccionado para ${rango.document_code_label}.`);
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible seleccionar el rango.');
    }
  };

  const handleDelete = async (rango: FacturacionRango) => {
    if (!window.confirm(`¿Eliminar rango ${rango.prefijo} (${rango.document_code_label})?`)) {
      return;
    }
    setActionMessage('');
    try {
      await configuracionAPI.eliminarRangoFacturacion(rango.id);
      setActionMessage('Rango eliminado correctamente.');
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible eliminar el rango.');
    }
  };

  const handleUpdateCurrent = async (rango: FacturacionRango) => {
    const value = window.prompt('Nuevo consecutivo', String(rango.consecutivo_actual));
    if (!value) return;
    setActionMessage('');
    try {
      await configuracionAPI.actualizarConsecutivoRango(rango.id, { current: Number(value), sync_local: true });
      setActionMessage(`Consecutivo actualizado para ${rango.prefijo}.`);
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible actualizar el consecutivo.');
    }
  };

  const syncAllRanges = async () => {
    setActionMessage('');
    try {
      await configuracionAPI.sincronizarRangosFacturacion();
      setActionMessage('Sincronización completada.');
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible sincronizar los rangos.');
    }
  };

  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
      <div className="grid gap-3 md:grid-cols-6">
        <Stat title="Entorno Factus" value={factusHealth?.environment || 'Desconocido'} />
        <Stat title="Estado token" value={factusHealth?.token_ok ? 'OK' : 'Sin validar'} />
        <Stat
          title="Última sincronización"
          value={stats.lastSync ? new Date(stats.lastSync).toLocaleString() : 'Sin datos'}
        />
        <Stat title="Rangos activos" value={stats.active} />
        <Stat title="Rangos vencidos" value={stats.expired} />
        <button
          type="button"
          onClick={syncAllRanges}
          disabled={!isAdmin || loading}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold"
        >
          <RefreshCw size={14} /> Sincronizar
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-lg px-3 py-1 text-xs font-semibold ${
              activeTab === tab.key ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error ? <p className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-sm text-red-600">{error}</p> : null}
      {degradedWarning ? (
        <p className="mt-3 rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-700">{degradedWarning}</p>
      ) : null}
      {actionMessage ? <p className="mt-3 rounded border border-blue-200 bg-blue-50 p-2 text-sm text-blue-700">{actionMessage}</p> : null}
      {loading ? <p className="mt-3 text-sm text-slate-600">Cargando...</p> : null}

      {(activeTab === 'resumen' || activeTab === 'consecutivos') && (
        <div className="mt-4 rounded-lg border border-slate-200 p-3">
          <p className="mb-3 text-sm font-semibold text-slate-800">Numeración local del sistema</p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs font-semibold text-slate-600">
              Prefijo factura local
              <input
                className="mt-1 w-full rounded border px-2 py-1"
                value={facturacion.prefijo_factura}
                onChange={(e) => onFacturacionChange({ ...facturacion, prefijo_factura: e.target.value })}
              />
            </label>
            <label className="text-xs font-semibold text-slate-600">
              Consecutivo factura local
              <input
                className="mt-1 w-full rounded border px-2 py-1"
                type="number"
                value={facturacion.numero_factura}
                onChange={(e) => onFacturacionChange({ ...facturacion, numero_factura: Number(e.target.value) })}
              />
            </label>
          </div>
          <button
            type="button"
            onClick={onSaveFacturacion}
            className="mt-3 inline-flex items-center gap-2 rounded bg-blue-600 px-3 py-2 text-xs font-semibold text-white"
          >
            <Save size={14} /> Guardar numeración local
          </button>
        </div>
      )}

      {activeTab === 'remisiones' && (
        <div className="mt-4 rounded-lg border border-slate-200 p-3">
          <p className="mb-2 text-sm font-semibold">Numeración local de remisiones</p>
          <div className="grid gap-2 md:grid-cols-2">
            <input className="rounded border px-2 py-1" placeholder="Prefijo remisión" value={remision.prefix || ''} onChange={(e) => setRemision((prev) => ({ ...prev, prefix: e.target.value }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Consecutivo remisión" value={remision.current || 1} onChange={(e) => setRemision((prev) => ({ ...prev, current: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Desde" value={remision.range_from || 1} onChange={(e) => setRemision((prev) => ({ ...prev, range_from: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Hasta" value={remision.range_to || 99999999} onChange={(e) => setRemision((prev) => ({ ...prev, range_to: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1 md:col-span-2" placeholder="Referencia administrativa" value={remision.resolution_reference || ''} onChange={(e) => setRemision((prev) => ({ ...prev, resolution_reference: e.target.value }))} />
            <textarea className="rounded border px-2 py-1 md:col-span-2" placeholder="Observaciones" value={remision.notes || ''} onChange={(e) => setRemision((prev) => ({ ...prev, notes: e.target.value }))} />
          </div>
          <button
            className="mt-3 inline-flex items-center gap-2 rounded bg-blue-600 px-3 py-2 text-xs font-semibold text-white"
            onClick={async () => {
              setActionMessage('');
              try {
                await configuracionAPI.actualizarNumeracionRemision(remision);
                setActionMessage('Numeración de remisiones guardada.');
                await loadData();
              } catch (e: unknown) {
                setActionMessage(getApiErrorMessage(e) || 'No fue posible guardar la numeración de remisiones.');
              }
            }}
            disabled={!isAdmin}
          ><Save size={14} /> Guardar</button>
        </div>
      )}

      {(activeTab === 'rangos' || activeTab === 'consecutivos' || activeTab === 'resumen') && (
        <div className="mt-4 overflow-auto rounded-lg border border-slate-200">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-50">
              <tr className="text-left text-slate-500">
                <th className="px-2 py-2">Tipo documento</th>
                <th className="px-2 py-2">Prefijo</th>
                <th className="px-2 py-2">Resolución</th>
                <th className="px-2 py-2">Desde</th>
                <th className="px-2 py-2">Hasta</th>
                <th className="px-2 py-2">Actual</th>
                <th className="px-2 py-2">Fecha vencimiento</th>
                <th className="px-2 py-2">Estado</th>
                <th className="px-2 py-2">Seleccionado local</th>
                <th className="px-2 py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rangos.map((rango) => (
                <tr key={rango.id} className="border-t border-slate-100">
                  <td className="px-2 py-2">{rango.document_code_label}</td>
                  <td className="px-2 py-2">{rango.prefijo}</td>
                  <td className="px-2 py-2">{rango.resolucion || '-'}</td>
                  <td className="px-2 py-2">{rango.desde}</td>
                  <td className="px-2 py-2">{rango.hasta}</td>
                  <td className="px-2 py-2">{rango.consecutivo_actual}</td>
                  <td className="px-2 py-2">{rango.fecha_expiracion || '-'}</td>
                  <td className="px-2 py-2">{rango.is_expired_remote ? 'Vencido' : rango.is_active_remote ? 'Activo' : 'Inactivo'}</td>
                  <td className="px-2 py-2">{rango.is_selected_local ? 'Sí' : 'No'}</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap gap-1">
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={async () => setDetalleRango(await configuracionAPI.obtenerDetalleRangoFacturacion(rango.id))}><Eye size={12} /></button>
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={() => handleSelect(rango)} disabled={!isAdmin}>Seleccionar activo</button>
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={() => handleUpdateCurrent(rango)} disabled={!isAdmin}>Actualizar consecutivo</button>
                      <button className="rounded bg-slate-100 px-2 py-1" onClick={syncAllRanges} disabled={!isAdmin}>Sincronizar</button>
                      <button className="rounded bg-red-100 px-2 py-1 text-red-700" onClick={() => handleDelete(rango)} disabled={!isAdmin}><Trash2 size={12} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detalleRango ? (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <div className="mb-2 flex items-center justify-between">
            <p className="font-semibold">Detalle rango seleccionado</p>
            <button className="rounded bg-white px-2 py-1" onClick={() => setDetalleRango(null)}>Cerrar</button>
          </div>
          <pre className="overflow-auto rounded bg-white p-2">{JSON.stringify(detalleRango, null, 2)}</pre>
        </div>
      ) : null}

      {softwareRows.length > 0 ? (
        <div className="mt-4 rounded-lg border border-slate-200 p-3 text-xs">
          <p className="font-semibold">Rangos asociados a software en Factus/DIAN</p>
          <p className="text-slate-500">Registros disponibles: {softwareRows.length}</p>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <p className="text-xs text-slate-500">{title}</p>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  );
}
