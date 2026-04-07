import { useEffect, useMemo, useState } from 'react';
import { Eye, Pencil, Plus, Save, Trash2 } from 'lucide-react';
import {
  configuracionAPI,
  type AuthorizedAvailableRange,
  type FacturacionRango,
} from '../../../api/configuracion';
import type { ConfiguracionFacturacion } from '../../../types';

type CreateTab = 'autorizado' | 'manual';

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

const DOC_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'FACTURA_VENTA', label: 'Factura de Venta', factusDocument: '21' },
  { value: 'NOTA_CREDITO', label: 'Nota Crédito', factusDocument: '22' },
  { value: 'NOTA_DEBITO', label: 'Nota Débito', factusDocument: '23' },
  { value: 'DOCUMENTO_SOPORTE', label: 'Documento Soporte', factusDocument: '24' },
  {
    value: 'NOTA_AJUSTE_DOCUMENTO_SOPORTE',
    label: 'Nota de Ajuste Documento Soporte',
    factusDocument: '95',
  },
  { value: 'NOMINA', label: 'Nómina', factusDocument: '9' },
  { value: 'NOTA_AJUSTE_NOMINA', label: 'Nota de Ajuste Nómina', factusDocument: '10' },
  {
    value: 'NOTA_ELIMINACION_NOMINA',
    label: 'Nota de eliminación de nómina',
    factusDocument: '11',
  },
  {
    value: 'FACTURA_TALONARIO',
    label: 'Factura de talonario o de papel',
    factusDocument: '27',
  },
] as const;

const STATUS_OPTIONS = [
  { value: 'todos', label: 'Todos' },
  { value: 'activo', label: 'Activados' },
  { value: 'inactivo', label: 'Desactivados' },
] as const;

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

const documentLabel = (documentCode: string) => {
  const found = DOC_OPTIONS.find((item) => item.value === documentCode);
  return found?.label ?? documentCode;
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
  const [rangos, setRangos] = useState<FacturacionRango[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingRemision, setSavingRemision] = useState(false);
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  const [docFilter, setDocFilter] = useState<string>('');
  const [stateFilter, setStateFilter] = useState<string>('activo');

  const [showModal, setShowModal] = useState(false);
  const [createTab, setCreateTab] = useState<CreateTab>('autorizado');
  const [form, setForm] = useState<RangoForm>(emptyForm);
  const [activateNow, setActivateNow] = useState(true);
  const [availableRanges, setAvailableRanges] = useState<AuthorizedAvailableRange[]>([]);
  const [detalleRango, setDetalleRango] = useState<Record<string, unknown> | null>(null);
  const [remision, setRemision] = useState<RemisionNumeracionPayload>({});

  const loadData = async () => {
    setLoading(true);
    setError('');

    const [rangosRes, remisionRes] = await Promise.allSettled([
      configuracionAPI.listarRangosFacturacion(),
      configuracionAPI.obtenerNumeracionRemision(),
    ]);

    if (rangosRes.status === 'fulfilled') {
      setRangos(rangosRes.value);
    } else {
      setError(rangosRes.reason?.response?.data?.detail || 'No fue posible cargar los rangos de numeración.');
    }

    if (remisionRes.status === 'fulfilled') {
      setRemision(remisionRes.value || {});
    }

    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredRangos = useMemo(() => {
    return rangos.filter((rango) => {
      const matchDocumento = !docFilter || rango.document_code === docFilter;
      const isActivo = Boolean(rango.activo);
      const matchEstado =
        stateFilter === 'todos' ? true : stateFilter === 'activo' ? isActivo : !isActivo;
      return matchDocumento && matchEstado;
    });
  }, [docFilter, rangos, stateFilter]);

  const paged = useMemo(() => filteredRangos.slice(0, 50), [filteredRangos]);

  const applyRemoteRange = (remote: AuthorizedAvailableRange) => {
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
      factus_id: Number(remote.factus_range_id || remote.remote_id || 0) || null,
      factus_range_id: Number(remote.factus_range_id || remote.remote_id || 0) || null,
    }));
    setAvailableRanges([]);
  };

  const handleBuscarRangosAutorizados = async () => {
    try {
      const response = await configuracionAPI.obtenerRangosAutorizadosDisponibles(form.document_code);
      setAvailableRanges(response.items || []);
      if (!response.items?.length) {
        setActionMessage(response.detail || 'No hay rangos asociados al software para este documento.');
      }
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible consultar rangos asociados.');
    }
  };

  const loadResolutionsByDocument = async (documentCode: string) => {
    try {
      const response = await configuracionAPI.obtenerRangosAutorizadosDisponibles(documentCode);
      setAvailableRanges(response.items || []);
      if (!response.items?.length) {
        setActionMessage(response.detail || 'No hay resoluciones vinculadas en Factus para este documento.');
      }
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible consultar resoluciones de Factus.');
      setAvailableRanges([]);
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

  useEffect(() => {
    if (!showModal || createTab !== 'autorizado') return;
    loadResolutionsByDocument(form.document_code);
  }, [form.document_code, showModal, createTab]);

  useEffect(() => {
    if (createTab !== 'manual') return;
    setAvailableRanges([]);
    setForm((prev) => ({
      ...prev,
      factus_id: null,
      factus_range_id: null,
    }));
  }, [createTab]);

  const toggleActivo = async (rango: FacturacionRango) => {
    try {
      const nextState = !rango.activo;
      if (!nextState && !window.confirm('¿Quieres desactivar este rango de numeración? Si estaba seleccionado, perderá la selección local.')) {
        return;
      }
      const selectNow = nextState && !rango.is_selected_local
        ? window.confirm('¿Deseas activar y seleccionar este rango para emisión?')
        : false;
      await configuracionAPI.activarYSeleccionarRangoFacturacion(rango.id, {
        activo: nextState,
        seleccionar: selectNow,
      });
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible actualizar el estado del rango.');
    }
  };

  const seleccionarRango = async (rango: FacturacionRango) => {
    try {
      await configuracionAPI.seleccionarRangoFacturacion(rango.id);
      setActionMessage(`Rango ${rango.prefijo} seleccionado localmente.`);
      await loadData();
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No fue posible seleccionar el rango.');
    }
  };

  const seleccionInconsistente = useMemo(() => {
    const grouped = new Map<string, FacturacionRango[]>();
    rangos.forEach((rango) => {
      const list = grouped.get(rango.document_code) || [];
      list.push(rango);
      grouped.set(rango.document_code, list);
    });
    const warnings: string[] = [];
    grouped.forEach((items, documentCode) => {
      const activos = items.filter((item) => item.activo && !item.is_expired_remote);
      const seleccionados = items.filter((item) => item.is_selected_local);
      if (activos.length > 1 && seleccionados.length === 0) {
        warnings.push(`${documentLabel(documentCode)}: hay ${activos.length} rangos activos sin selección local.`);
      }
    });
    return warnings;
  }, [rangos]);

  const saveRemision = async () => {
    setSavingRemision(true);
    try {
      await configuracionAPI.actualizarNumeracionRemision({
        prefix: remision.prefix || 'REM',
        current: remision.current || 1,
        range_from: remision.range_from || 1,
        range_to: remision.range_to || 99999999,
        resolution_reference: remision.resolution_reference || '',
        notes: remision.notes || '',
      });
      setActionMessage('Numeración de remisiones actualizada.');
    } catch (e: unknown) {
      setActionMessage(getApiErrorMessage(e) || 'No se pudo actualizar numeración de remisiones.');
    } finally {
      setSavingRemision(false);
    }
  };

  return (
    <section className="rounded-2xl bg-white p-0 shadow-sm">
      <div className="border-b border-slate-200 bg-slate-100 px-5 py-4">
        <h3 className="text-4 font-semibold text-slate-700">Rangos de numeración</h3>
      </div>

      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-52 text-sm font-semibold text-slate-700">
            Tipo de documento
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-600 focus:outline-none"
              value={docFilter}
              onChange={(e) => setDocFilter(e.target.value)}
            >
              {DOC_OPTIONS.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="min-w-40 text-sm font-semibold text-slate-700">
            Estado
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-600 focus:outline-none"
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="ml-auto inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => setShowModal(true)}
            disabled={!isAdmin}
          >
            <Plus size={16} /> Nuevo rango de numeración
          </button>
        </div>

        {error ? <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
        {actionMessage ? (
          <p className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{actionMessage}</p>
        ) : null}
        {seleccionInconsistente.length ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <p className="font-semibold">Atención: hay rangos activos sin selección local.</p>
            <ul className="list-disc pl-5">
              {seleccionInconsistente.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Documento</th>
                <th className="px-4 py-3">Prefijo</th>
                <th className="px-4 py-3">Desde</th>
                <th className="px-4 py-3">Hasta</th>
                <th className="px-4 py-3">Actual</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Vence en</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={8}>
                    Cargando rangos...
                  </td>
                </tr>
              ) : paged.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={8}>
                    No hay rangos disponibles para el filtro seleccionado.
                  </td>
                </tr>
              ) : (
                paged.map((rango) => {
                  const marked = rango.is_expired_remote || !rango.activo;
                  const expiryDate = rango.fecha_expiracion ? new Date(`${rango.fecha_expiracion}T00:00:00`) : null;
                  const isExpiredByDate = expiryDate ? expiryDate.getTime() < Date.now() : false;
                  const canSelectFacturaVenta =
                    rango.document_code !== 'FACTURA_VENTA'
                    || Boolean(
                      rango.factus_range_id
                      && rango.is_associated_to_software
                      && rango.is_active_remote
                      && !rango.is_expired_remote
                      && !isExpiredByDate,
                    );
                  return (
                    <tr key={rango.id} className={`border-t border-slate-100 ${marked ? 'bg-red-200/70' : 'hover:bg-slate-50'}`}>
                      <td className="px-4 py-3 text-slate-700">{rango.document_code_label || documentLabel(rango.document_code)}</td>
                      <td className="px-4 py-3 text-slate-700">
                        <div className="flex items-center gap-2">
                          <span>{rango.prefijo || 'N/A'}</span>
                          {rango.is_selected_local ? (
                            <span className="rounded-full bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700">Seleccionado</span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-700">{rango.desde || 'N/A'}</td>
                      <td className="px-4 py-3 text-slate-700">{rango.hasta || 'N/A'}</td>
                      <td className="px-4 py-3 text-slate-700">{rango.consecutivo_actual || 'N/A'}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => toggleActivo(rango)}
                            disabled={!isAdmin}
                            className={`min-w-14 rounded-full px-3 py-1 text-xs font-semibold text-white ${
                              rango.activo ? 'bg-blue-600' : 'bg-slate-400'
                            } disabled:cursor-not-allowed disabled:opacity-60`}
                          >
                            {rango.activo ? 'ON' : 'OFF'}
                          </button>
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${rango.activo ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
                            {rango.activo ? 'Activo' : 'Inactivo'}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-700">{rango.fecha_expiracion || 'N/A'}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            className="rounded-md border border-indigo-200 px-2 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
                            title="Seleccionar para emisión"
                            onClick={() => seleccionarRango(rango)}
                            disabled={!isAdmin || !rango.activo || rango.is_expired_remote || isExpiredByDate || !canSelectFacturaVenta}
                          >
                            Seleccionar
                          </button>
                          <button
                            type="button"
                            className="rounded-md p-1 text-blue-600 hover:bg-blue-50"
                            title="Editar"
                            onClick={() => setDetalleRango(rango)}
                          >
                            <Pencil size={16} />
                          </button>
                          <button
                            type="button"
                            className="rounded-md p-1 text-emerald-600 hover:bg-emerald-50"
                            title="Ver detalle"
                            onClick={async () => {
                              const detalle = await configuracionAPI.obtenerDetalleRangoFacturacion(rango.id);
                              setDetalleRango(detalle);
                            }}
                          >
                            <Eye size={16} />
                          </button>
                          <button
                            type="button"
                            className="rounded-md p-1 text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                            title="Eliminar"
                            onClick={() => configuracionAPI.eliminarRangoFacturacion(rango.id).then(loadData)}
                            disabled={!isAdmin}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-semibold text-slate-700">Numeración local y remisiones</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Input
              label="Prefijo factura local"
              value={facturacion.prefijo_factura}
              onChange={(v) => onFacturacionChange({ ...facturacion, prefijo_factura: v })}
            />
            <Input
              label="Consecutivo factura local"
              type="number"
              value={String(facturacion.numero_factura)}
              onChange={(v) => onFacturacionChange({ ...facturacion, numero_factura: Number(v) || 0 })}
            />
            <Input
              label="Prefijo remisión"
              value={remision.prefix || facturacion.prefijo_remision || ''}
              onChange={(v) => setRemision((prev) => ({ ...prev, prefix: v }))}
            />
            <Input
              label="Consecutivo remisión"
              type="number"
              value={String(remision.current || facturacion.numero_remision || 1)}
              onChange={(v) => setRemision((prev) => ({ ...prev, current: Number(v) || 1 }))}
            />
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onSaveFacturacion}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              <Save size={16} /> Guardar configuración
            </button>
            <button
              type="button"
              onClick={saveRemision}
              disabled={savingRemision || !isAdmin}
              className="inline-flex items-center gap-2 rounded-lg border border-blue-200 px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Save size={16} /> {savingRemision ? 'Guardando...' : 'Guardar remisiones'}
            </button>
          </div>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-3">
          <div className="w-full max-w-6xl rounded-xl bg-[#f8fafc] p-4">
            <h3 className="text-2xl font-semibold text-slate-700">Nuevo rango de numeración</h3>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <button
                className={`rounded px-3 py-2 text-lg font-semibold text-white ${
                  createTab === 'autorizado' ? 'bg-blue-700' : 'bg-blue-400'
                }`}
                onClick={() => setCreateTab('autorizado')}
              >
                Rango autorizado
              </button>
              <button
                className={`rounded px-3 py-2 text-lg font-semibold text-white ${
                  createTab === 'manual' ? 'bg-blue-700' : 'bg-blue-400'
                }`}
                onClick={() => setCreateTab('manual')}
              >
                Rango manual
              </button>
            </div>

            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-sm font-semibold text-slate-700">
                  Documento
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-blue-600 focus:outline-none"
                    value={form.document_code}
                    onChange={(e) => setForm((prev) => ({ ...prev, document_code: e.target.value }))}
                  >
                    {DOC_OPTIONS.filter((item) => item.value).map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </label>

                {createTab === 'autorizado' ? (
                  <div className="flex items-end">
                    <button
                      className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                      onClick={handleBuscarRangosAutorizados}
                    >
                      Buscar
                    </button>
                  </div>
                ) : null}

                <Input label="Prefijo" value={form.prefijo} onChange={(v) => setForm((prev) => ({ ...prev, prefijo: v }))} />
                <Input label="Desde" type="number" value={String(form.desde)} onChange={(v) => setForm((prev) => ({ ...prev, desde: Number(v) }))} />
                <Input label="Hasta" type="number" value={String(form.hasta)} onChange={(v) => setForm((prev) => ({ ...prev, hasta: Number(v) }))} />
                <Input
                  label="Número actual"
                  type="number"
                  value={String(form.consecutivo_actual)}
                  onChange={(v) => setForm((prev) => ({ ...prev, consecutivo_actual: Number(v) }))}
                />
                <Input label="Número de resolución" value={form.resolucion} onChange={(v) => setForm((prev) => ({ ...prev, resolucion: v }))} />
                <Input
                  label="Fecha de expedición"
                  type="date"
                  value={form.fecha_autorizacion}
                  onChange={(v) => setForm((prev) => ({ ...prev, fecha_autorizacion: v }))}
                />
                <Input
                  label="Fecha de vencimiento"
                  type="date"
                  value={form.fecha_expiracion}
                  onChange={(v) => setForm((prev) => ({ ...prev, fecha_expiracion: v }))}
                />
                <div className="md:col-span-2">
                  <Input label="Clave técnica" value={form.technical_key} onChange={(v) => setForm((prev) => ({ ...prev, technical_key: v }))} />
                </div>
                <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700 md:col-span-2">
                  <input
                    type="checkbox"
                    checked={activateNow}
                    onChange={(e) => setActivateNow(e.target.checked)}
                  />
                  Seleccionar como rango local activo al registrar
                </label>
              </div>
            </div>

            {createTab === 'autorizado' ? (
              <div className="mt-3 rounded-lg border bg-white p-4">
                <p className="mb-2 text-base font-semibold text-slate-700">
                  Resoluciones vinculadas en Factus
                </p>
                <p className="mb-2 text-sm font-medium text-slate-600">
                  Selecciona una resolución para autocompletar el rango.
                </p>
                {availableRanges.length > 0 ? (
                  <div className="max-h-44 overflow-auto rounded border p-2">
                    {availableRanges.map((item) => (
                      <button
                        key={String(item.remote_id)}
                        className="block w-full rounded px-2 py-1 text-left text-lg font-semibold text-slate-700 hover:bg-blue-50"
                        onClick={() => applyRemoteRange(item)}
                      >
                        {String(item.prefix || '')} ({String(item.from || '')} - {String(item.to || '')})
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500">
                    No hay resoluciones vinculadas para el documento seleccionado.
                  </p>
                )}
              </div>
            ) : null}

            <div className="mt-4 flex justify-end gap-2">
              <button className="rounded border px-3 py-2 text-sm" onClick={() => setShowModal(false)}>
                Cerrar
              </button>
              <button
                className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                onClick={handleCreate}
              >
                Registrar
              </button>
            </div>
          </div>
        </div>
      )}

      {detalleRango ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/35 p-4">
          <div className="w-full max-w-2xl rounded-xl bg-white p-4 shadow-xl">
            <div className="flex items-start justify-between">
              <h4 className="text-lg font-semibold text-slate-800">Detalle del rango</h4>
              <button className="rounded border px-2 py-1 text-xs" onClick={() => setDetalleRango(null)}>
                Cerrar
              </button>
            </div>
            <pre className="mt-3 max-h-[65vh] overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
              {JSON.stringify(detalleRango, null, 2)}
            </pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Input({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <label className="text-sm font-semibold text-slate-700">
      {label}
      <input
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-600 focus:outline-none"
        value={value}
        type={type}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
