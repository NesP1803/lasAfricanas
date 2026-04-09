import { type FormEvent, type ReactNode, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Save } from 'lucide-react';
import type { ConfiguracionFacturacion } from '../../../types';

type Props = {
  isAdmin: boolean;
  facturacion: ConfiguracionFacturacion;
  onFacturacionChange: (next: ConfiguracionFacturacion) => void;
  onSaveFacturacion: () => Promise<void>;
};

const TECH_STATUS_OK = (facturacion: ConfiguracionFacturacion) =>
  ['factura_venta', 'nota_credito', 'nota_debito', 'documento_soporte', 'nota_ajuste_documento_soporte']
    .some((doc) => Boolean((facturacion as Record<string, unknown>)[`factus_${doc}_is_valid`]));

const DOCUMENTS = [
  { key: 'factura_venta', label: 'Factura de venta' },
  { key: 'nota_credito', label: 'Nota crédito' },
  { key: 'nota_debito', label: 'Nota débito' },
  { key: 'documento_soporte', label: 'Documento soporte' },
  { key: 'nota_ajuste_documento_soporte', label: 'Nota ajuste documento soporte' },
] as const;

export default function FacturacionElectronicaAdmin({
  isAdmin,
  facturacion,
  onFacturacionChange,
  onSaveFacturacion,
}: Props) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const remisionSiguiente = useMemo(() => (Number(facturacion.numero_remision || 1) + 1), [facturacion.numero_remision]);
  const cotizacionSiguiente = useMemo(() => (Number(facturacion.numero_cotizacion || 1) + 1), [facturacion.numero_cotizacion]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      await onSaveFacturacion();
      setMessage('Numeración interna actualizada correctamente.');
    } catch {
      setMessage('No fue posible guardar la configuración.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="space-y-4 rounded-2xl bg-white p-5 shadow-sm">
      <div className="border-b border-slate-200 pb-4">
        <h3 className="text-lg font-semibold text-slate-900">Configuración de facturación</h3>
        <p className="mt-1 text-sm text-slate-500">
          Se separa la configuración técnica de emisión electrónica de la numeración interna del sistema.
        </p>
      </div>

      {message ? (
        <p className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</p>
      ) : null}

      <div className="rounded-xl border border-slate-200 p-4">
        <h4 className="text-sm font-semibold text-slate-800">Rangos técnicos Factus por documento electrónico</h4>
        <div className="mt-4 space-y-4">
          {DOCUMENTS.map((document) => {
            const id = (facturacion as Record<string, unknown>)[`factus_numbering_range_id_${document.key}`] as number | null | undefined;
            const prefix = (facturacion as Record<string, unknown>)[`factus_${document.key}_range_prefix`] as string | undefined;
            const resolution = (facturacion as Record<string, unknown>)[`factus_${document.key}_resolution_number`] as string | undefined;
            const from = (facturacion as Record<string, unknown>)[`factus_${document.key}_range_from`] as number | null | undefined;
            const to = (facturacion as Record<string, unknown>)[`factus_${document.key}_range_to`] as number | null | undefined;
            const validFrom = (facturacion as Record<string, unknown>)[`factus_${document.key}_valid_from`] as string | null | undefined;
            const validTo = (facturacion as Record<string, unknown>)[`factus_${document.key}_valid_to`] as string | null | undefined;
            const current = (facturacion as Record<string, unknown>)[`factus_${document.key}_current`] as number | null | undefined;
            const isValid = Boolean((facturacion as Record<string, unknown>)[`factus_${document.key}_is_valid`]);
            const environment = ((facturacion as Record<string, unknown>)[`factus_${document.key}_environment`] as string | undefined) || facturacion.ambiente_factus || 'No disponible';
            return (
              <div key={document.key} className="rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-semibold text-slate-800">{document.label}</p>
                <div className="mt-2 grid gap-3 md:grid-cols-2">
                  <Info label="Ambiente" value={environment} />
                  <Info label="Estado" value={isValid ? 'Válida' : 'Inválida'} icon={isValid ? <CheckCircle2 size={14} className="text-emerald-600" /> : <AlertCircle size={14} className="text-amber-600" />} />
                  <Info label="ID técnico activo" value={id ? `ID ${id}` : 'No encontrado'} />
                  <Info label="Prefijo" value={prefix || (document.key === 'factura_venta' ? facturacion.prefijo_factura_electronica || '' : '') || 'No disponible'} />
                  <Info label="Resolución" value={resolution || 'No disponible'} />
                  <Info label="Rango" value={from && to ? `${from} - ${to}` : 'No disponible'} />
                  <Info label="Vigencia" value={validFrom && validTo ? `${validFrom} a ${validTo}` : 'No disponible'} />
                  <Info label="Último número conocido" value={current ? String(current) : 'No disponible'} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <form className="rounded-xl border border-slate-200 p-4" onSubmit={handleSubmit}>
        <h4 className="text-sm font-semibold text-slate-800">Numeración interna</h4>
        <p className="mt-1 text-sm text-slate-500">Solo aplica para remisiones y cotizaciones.</p>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Input
            label="Prefijo remisión"
            value={facturacion.prefijo_remision || ''}
            onChange={(v) => onFacturacionChange({ ...facturacion, prefijo_remision: v.toUpperCase().replace(/[^A-Z0-9-]/g, '').slice(0, 10) })}
            disabled={!isAdmin}
          />
          <Input
            label="Consecutivo remisión"
            type="number"
            value={String(facturacion.numero_remision || 1)}
            onChange={(v) => onFacturacionChange({ ...facturacion, numero_remision: Math.max(1, Number(v) || 1) })}
            disabled={!isAdmin}
          />
          <Input
            label="Prefijo cotización"
            value={facturacion.prefijo_cotizacion || 'COT'}
            onChange={(v) => onFacturacionChange({ ...facturacion, prefijo_cotizacion: v.toUpperCase().replace(/[^A-Z0-9-]/g, '').slice(0, 10) })}
            disabled={!isAdmin}
          />
          <Input
            label="Consecutivo cotización"
            type="number"
            value={String(facturacion.numero_cotizacion || 1)}
            onChange={(v) => onFacturacionChange({ ...facturacion, numero_cotizacion: Math.max(1, Number(v) || 1) })}
            disabled={!isAdmin}
          />
        </div>

        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          <p>Vista previa siguiente remisión: <strong>{(facturacion.prefijo_remision || 'REM')}-{remisionSiguiente}</strong></p>
          <p>Vista previa siguiente cotización: <strong>{(facturacion.prefijo_cotizacion || 'COT')}-{cotizacionSiguiente}</strong></p>
        </div>

        <button
          type="submit"
          disabled={!isAdmin || saving}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Save size={16} /> {saving ? 'Guardando...' : 'Guardar'}
        </button>
      </form>
    </section>
  );
}

function Info({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 inline-flex items-center gap-2">{icon}{value}</p>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  type = 'text',
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <label className="text-sm font-semibold text-slate-700">
      {label}
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-600 focus:outline-none disabled:bg-slate-100"
      />
    </label>
  );
}
