import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw, Save, Trash2 } from 'lucide-react';
import { configuracionAPI, type FacturacionRango } from '../../../api/configuracion';

type TabKey = 'resumen' | 'rangos' | 'resoluciones' | 'consecutivos' | 'software' | 'remisiones' | 'historial';

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'resumen', label: 'Resumen' },
  { key: 'rangos', label: 'Rangos electrónicos' },
  { key: 'resoluciones', label: 'Resoluciones' },
  { key: 'consecutivos', label: 'Consecutivos' },
  { key: 'software', label: 'Software DIAN' },
  { key: 'remisiones', label: 'Remisiones' },
  { key: 'historial', label: 'Historial / auditoría' },
];

const documentLabels: Record<string, string> = {
  FACTURA_VENTA: 'Factura de venta',
  NOTA_CREDITO: 'Nota crédito',
  NOTA_DEBITO: 'Nota débito',
  DOCUMENTO_SOPORTE: 'Documento soporte',
  NOTA_AJUSTE_DOCUMENTO_SOPORTE: 'Nota ajuste doc soporte',
};

export default function FacturacionElectronicaAdmin({ isAdmin }: { isAdmin: boolean }) {
  const [activeTab, setActiveTab] = useState<TabKey>('resumen');
  const [rangos, setRangos] = useState<FacturacionRango[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [softwareRows, setSoftwareRows] = useState<any[]>([]);
  const [remision, setRemision] = useState<any>({});
  const [historialRemision, setHistorialRemision] = useState<any[]>([]);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [rangosData, softwareData, remisionData, remisionHistorial] = await Promise.all([
        configuracionAPI.listarRangosFacturacion(),
        configuracionAPI.obtenerRangosSoftware(),
        configuracionAPI.obtenerNumeracionRemision(),
        configuracionAPI.obtenerHistorialRemision(),
      ]);
      setRangos(rangosData);
      setSoftwareRows(Array.isArray(softwareData) ? softwareData : []);
      setRemision(remisionData || {});
      setHistorialRemision(Array.isArray(remisionHistorial) ? remisionHistorial : []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'No fue posible cargar la configuración de facturación.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const stats = useMemo(() => {
    const active = rangos.filter((r) => r.is_active_remote).length;
    const expired = rangos.filter((r) => r.is_expired_remote).length;
    const near = rangos.filter((r) => r.is_near_expiration).length;
    const desync = rangos.filter((r) => !r.is_associated_to_software).length;
    return { active, expired, near, desync };
  }, [rangos]);

  const handleSelect = async (rango: FacturacionRango) => {
    await configuracionAPI.seleccionarActivoRangoFacturacion(rango.id, rango.document_code);
    await loadData();
  };

  const handleDelete = async (rango: FacturacionRango) => {
    await configuracionAPI.eliminarRangoFacturacion(rango.id);
    await loadData();
  };

  const handleUpdateCurrent = async (rango: FacturacionRango) => {
    const value = window.prompt('Nuevo consecutivo', String(rango.consecutivo_actual));
    if (!value) return;
    await configuracionAPI.actualizarConsecutivoRango(rango.id, { current: Number(value), sync_local: true });
    await loadData();
  };

  const groupedResolutions = useMemo(() => {
    const map = new Map<string, FacturacionRango[]>();
    rangos.forEach((r) => {
      const key = r.resolucion || 'Sin resolución';
      map.set(key, [...(map.get(key) || []), r]);
    });
    return Array.from(map.entries());
  }, [rangos]);

  return (
    <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4">
      <div className="grid gap-3 md:grid-cols-6">
        <Stat title="Rangos activos" value={stats.active} />
        <Stat title="Rangos vencidos" value={stats.expired} />
        <Stat title="Por vencer" value={stats.near} />
        <Stat title="Desincronizados" value={stats.desync} />
        <Stat title="Token" value={error ? 'Error' : 'OK'} />
        <button
          type="button"
          onClick={async () => {
            await configuracionAPI.sincronizarRangosFacturacion();
            await loadData();
          }}
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

      {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
      {loading ? <p className="mt-3 text-sm text-slate-600">Cargando...</p> : null}

      {activeTab === 'resumen' && (
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          {['FACTURA_VENTA', 'NOTA_CREDITO', 'NOTA_DEBITO', 'DOCUMENTO_SOPORTE'].map((code) => {
            const selected = rangos.find((item) => item.document_code === code && item.is_selected_local);
            return (
              <div key={code} className="rounded-lg border border-slate-200 p-3">
                <p className="text-xs text-slate-500">{documentLabels[code]}</p>
                <p className="font-semibold">{selected ? `${selected.prefijo} (${selected.consecutivo_actual})` : 'Sin selección local'}</p>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'rangos' && (
        <div className="mt-4 overflow-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="text-left text-slate-500">
                <th>ID</th><th>Documento</th><th>Prefijo</th><th>Resolución</th><th>Desde</th><th>Hasta</th><th>Current</th><th>Estado</th><th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {rangos.map((rango) => (
                <tr key={rango.id} className="border-t border-slate-100">
                  <td>{rango.id_factus}</td>
                  <td>{rango.document_name}</td>
                  <td>{rango.prefijo}</td>
                  <td>{rango.resolucion || '-'}</td>
                  <td>{rango.desde}</td>
                  <td>{rango.hasta}</td>
                  <td>{rango.consecutivo_actual}</td>
                  <td>{rango.is_expired_remote ? 'Vencido' : rango.is_active_remote ? 'Activo' : 'Inactivo'}</td>
                  <td>
                    <div className="flex gap-1">
                      <button className="rounded bg-slate-100 px-2" onClick={() => handleSelect(rango)} disabled={!isAdmin}>Seleccionar</button>
                      <button className="rounded bg-slate-100 px-2" onClick={() => handleUpdateCurrent(rango)} disabled={!isAdmin}>Consecutivo</button>
                      <button className="rounded bg-red-100 px-2 text-red-700" onClick={() => handleDelete(rango)} disabled={!isAdmin}><Trash2 size={12} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'resoluciones' && (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {groupedResolutions.map(([resolution, rows]) => (
            <div key={resolution} className="rounded-lg border border-slate-200 p-3">
              <p className="font-semibold">Resolución {resolution}</p>
              <p className="text-xs text-slate-500">Rangos: {rows.length}</p>
              <p className="text-xs text-slate-500">Prefijos: {rows.map((r) => r.prefijo).join(', ')}</p>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'consecutivos' && (
        <div className="mt-4 space-y-2">
          {rangos.map((rango) => (
            <div key={rango.id} className="flex items-center justify-between rounded border border-slate-200 p-2 text-sm">
              <div>
                <p className="font-medium">{rango.prefijo} · {rango.document_name}</p>
                <p className="text-xs text-slate-500">Remoto/local actual: {rango.consecutivo_actual}</p>
              </div>
              <button className="rounded bg-slate-100 px-2 py-1 text-xs" onClick={() => handleUpdateCurrent(rango)} disabled={!isAdmin}>Actualizar consecutivo</button>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'software' && (
        <div className="mt-4 space-y-2 text-xs">
          {softwareRows.map((row, index) => (
            <div key={index} className="rounded border border-slate-200 p-2">
              <p className="font-semibold">{row?.remote?.prefix || '-'}</p>
              <p>Resolución: {row?.remote?.resolution_number || '-'}</p>
              <p>Coincidencia local: {row?.matches_local ? 'Sí' : 'No'}</p>
              {Array.isArray(row?.differences) && row.differences.length > 0 ? (
                <p className="text-amber-700 inline-flex items-center gap-1"><AlertTriangle size={12} /> Diferencias: {row.differences.join(', ')}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'remisiones' && (
        <div className="mt-4 rounded-lg border border-slate-200 p-3">
          <p className="mb-2 text-sm font-semibold">Numeración local de remisiones (independiente de Factus)</p>
          <div className="grid gap-2 md:grid-cols-2">
            <input className="rounded border px-2 py-1" placeholder="Prefijo" value={remision.prefix || ''} onChange={(e) => setRemision((prev: any) => ({ ...prev, prefix: e.target.value }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Consecutivo" value={remision.current || 1} onChange={(e) => setRemision((prev: any) => ({ ...prev, current: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Desde" value={remision.range_from || 1} onChange={(e) => setRemision((prev: any) => ({ ...prev, range_from: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1" type="number" placeholder="Hasta" value={remision.range_to || 99999999} onChange={(e) => setRemision((prev: any) => ({ ...prev, range_to: Number(e.target.value) }))} />
            <input className="rounded border px-2 py-1 md:col-span-2" placeholder="Referencia resolución interna" value={remision.resolution_reference || ''} onChange={(e) => setRemision((prev: any) => ({ ...prev, resolution_reference: e.target.value }))} />
            <textarea className="rounded border px-2 py-1 md:col-span-2" placeholder="Notas" value={remision.notes || ''} onChange={(e) => setRemision((prev: any) => ({ ...prev, notes: e.target.value }))} />
          </div>
          <button
            className="mt-3 inline-flex items-center gap-2 rounded bg-blue-600 px-3 py-2 text-xs font-semibold text-white"
            onClick={async () => {
              await configuracionAPI.actualizarNumeracionRemision(remision);
              await loadData();
            }}
            disabled={!isAdmin}
          ><Save size={14} /> Guardar remisión</button>
        </div>
      )}

      {activeTab === 'historial' && (
        <div className="mt-4 space-y-2 text-xs">
          {historialRemision.map((item) => (
            <div key={item.id} className="rounded border border-slate-200 p-2">
              <p className="font-semibold">{item.changed_by_name || 'Sistema'}</p>
              <p>{new Date(item.changed_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      <p className="text-xs text-slate-500">{title}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}
