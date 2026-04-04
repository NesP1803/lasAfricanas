import type { EstadoDian } from '../services/notasCreditoApi';

const estadoStyles: Record<string, string> = {
  ACEPTADA: 'bg-emerald-100 text-emerald-700',
  ACEPTADA_CON_OBSERVACIONES: 'bg-emerald-100 text-emerald-700',
  PENDIENTE_ENVIO: 'bg-blue-100 text-blue-700',
  PENDIENTE_DIAN: 'bg-amber-100 text-amber-700',
  EN_PROCESO: 'bg-amber-100 text-amber-700',
  CONFLICTO_FACTUS: 'bg-orange-100 text-orange-700',
  PENDIENTE_REINTENTO: 'bg-amber-100 text-amber-700',
  RECHAZADA: 'bg-rose-100 text-rose-700',
  ERROR_INTEGRACION: 'bg-rose-100 text-rose-700',
  ERROR_PERSISTENCIA: 'bg-rose-100 text-rose-700',
  BORRADOR: 'bg-slate-100 text-slate-700',
  ANULADA_LOCAL: 'bg-slate-200 text-slate-700',
  ERROR: 'bg-slate-200 text-slate-700',
};

export const resolveEstadoNota = ({ estado, estado_local, estado_dian }: { estado?: string; estado_local?: string; estado_dian?: string }) =>
  {
    const raw = (estado_local || estado || estado_dian || 'ERROR').toUpperCase();
    if (['PENDIENTE_ENVIO', 'PENDIENTE_DIAN', 'CONFLICTO_FACTUS', 'ERROR_INTEGRACION', 'PENDIENTE_REINTENTO'].includes(raw)) {
      return 'EN_PROCESO';
    }
    return raw;
  };

export default function EstadoNotaCreditoBadge({ estado }: { estado: EstadoDian }) {
  const normalizedEstado = estado?.toUpperCase() ?? 'ERROR';
  const style = estadoStyles[normalizedEstado] ?? estadoStyles.ERROR;
  const label = normalizedEstado === 'CONFLICTO_FACTUS'
    ? 'CONFLICTO FACTUS (SIN CONFIRMACIÓN)'
      : normalizedEstado === 'PENDIENTE_DIAN'
      ? 'EN PROCESO (DIAN)'
      : normalizedEstado === 'EN_PROCESO'
        ? 'EN PROCESO'
      : normalizedEstado.replaceAll('_', ' ');

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>
      {label}
    </span>
  );
}
