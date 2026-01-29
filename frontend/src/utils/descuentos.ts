export type EstadoSolicitudDescuento = 'PENDIENTE' | 'APROBADO' | 'RECHAZADO';

export interface SolicitudDescuento {
  id: string;
  solicitanteId: number;
  solicitanteNombre: string;
  aprobadorId: number;
  aprobadorNombre: string;
  descuentoSolicitado: number;
  descuentoAprobado?: number;
  estado: EstadoSolicitudDescuento;
  createdAt: string;
  updatedAt: string;
}

export const DESCUENTO_STORAGE_KEY = 'solicitudes_descuento';

const buildId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `sol-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
};

const safeParse = (raw: string | null): SolicitudDescuento[] => {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as SolicitudDescuento[];
    if (Array.isArray(parsed)) {
      return parsed;
    }
    return [];
  } catch (error) {
    return [];
  }
};

export const cargarSolicitudes = (): SolicitudDescuento[] => {
  if (typeof window === 'undefined') return [];
  return safeParse(window.localStorage.getItem(DESCUENTO_STORAGE_KEY));
};

export const guardarSolicitudes = (solicitudes: SolicitudDescuento[]) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(DESCUENTO_STORAGE_KEY, JSON.stringify(solicitudes));
};

export const crearSolicitud = (payload: {
  solicitanteId: number;
  solicitanteNombre: string;
  aprobadorId: number;
  aprobadorNombre: string;
  descuentoSolicitado: number;
}): SolicitudDescuento[] => {
  const solicitudes = cargarSolicitudes();
  const ahora = new Date().toISOString();
  const nuevaSolicitud: SolicitudDescuento = {
    id: buildId(),
    solicitanteId: payload.solicitanteId,
    solicitanteNombre: payload.solicitanteNombre,
    aprobadorId: payload.aprobadorId,
    aprobadorNombre: payload.aprobadorNombre,
    descuentoSolicitado: payload.descuentoSolicitado,
    estado: 'PENDIENTE',
    createdAt: ahora,
    updatedAt: ahora,
  };
  const next = [nuevaSolicitud, ...solicitudes];
  guardarSolicitudes(next);
  return next;
};

export const actualizarSolicitud = (
  id: string,
  cambios: Partial<Pick<SolicitudDescuento, 'estado' | 'descuentoAprobado'>>
): SolicitudDescuento[] => {
  const solicitudes = cargarSolicitudes();
  const ahora = new Date().toISOString();
  const next = solicitudes.map((solicitud) =>
    solicitud.id === id
      ? {
          ...solicitud,
          ...cambios,
          updatedAt: ahora,
        }
      : solicitud
  );
  guardarSolicitudes(next);
  return next;
};

export const obtenerSolicitudesPorAprobador = (aprobadorId: number) =>
  cargarSolicitudes().filter((solicitud) => solicitud.aprobadorId === aprobadorId);

export const obtenerUltimaSolicitudPorUsuario = (solicitanteId: number) => {
  const solicitudes = cargarSolicitudes().filter(
    (solicitud) => solicitud.solicitanteId === solicitanteId
  );
  if (solicitudes.length === 0) return null;
  return solicitudes.reduce((latest, solicitud) =>
    solicitud.updatedAt > latest.updatedAt ? solicitud : latest
  );
};
