import type { EstadoDian } from '../services/notasCreditoApi';

const estadoStyles: Record<string, string> = {
  ACEPTADA: 'bg-emerald-100 text-emerald-700',
  ACEPTADA_CON_OBSERVACIONES: 'bg-emerald-100 text-emerald-700',
  ENVIADA_A_FACTUS: 'bg-blue-100 text-blue-700',
  EN_PROCESO: 'bg-amber-100 text-amber-700',
  PENDIENTE_REINTENTO: 'bg-amber-100 text-amber-700',
  RECHAZADA: 'bg-rose-100 text-rose-700',
  ERROR_INTEGRACION: 'bg-rose-100 text-rose-700',
  ERROR_PERSISTENCIA: 'bg-rose-100 text-rose-700',
  BORRADOR: 'bg-slate-100 text-slate-700',
  ERROR: 'bg-slate-200 text-slate-700',
};

export const resolveEstadoNota = ({ estado, estado_local, estado_dian }: { estado?: string; estado_local?: string; estado_dian?: string }) =>
  (estado_local || estado || estado_dian || 'ERROR').toUpperCase();

export default function EstadoNotaCreditoBadge({ estado }: { estado: EstadoDian }) {
  const normalizedEstado = estado?.toUpperCase() ?? 'ERROR';
  const style = estadoStyles[normalizedEstado] ?? estadoStyles.ERROR;

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>
      {normalizedEstado.replaceAll('_', ' ')}
    </span>
  );
}
