import type { EstadoDian } from '../services/facturacionApi';

interface EstadoDIANBadgeProps {
  estado: EstadoDian;
}

const estadoStyles: Record<string, string> = {
  ACEPTADA: 'bg-emerald-100 text-emerald-700',
  RECHAZADA: 'bg-red-100 text-red-700',
  EN_PROCESO: 'bg-amber-100 text-amber-700',
  ERROR: 'bg-slate-200 text-slate-700',
};

export default function EstadoDIANBadge({ estado }: EstadoDIANBadgeProps) {
  const normalizedEstado = estado?.toUpperCase() ?? 'ERROR';
  const style = estadoStyles[normalizedEstado] ?? estadoStyles.ERROR;

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${style}`}>
      {normalizedEstado.replaceAll('_', ' ')}
    </span>
  );
}
