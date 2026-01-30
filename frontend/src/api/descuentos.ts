import apiClient from './client';

export type EstadoSolicitudDescuento = 'PENDIENTE' | 'APROBADO' | 'RECHAZADO';

export interface SolicitudDescuento {
  id: number;
  vendedor: number;
  vendedor_nombre: string;
  aprobador: number;
  aprobador_nombre: string;
  descuento_solicitado: string;
  descuento_aprobado?: string | null;
  subtotal?: string | null;
  iva?: string | null;
  total_antes_descuento?: string | null;
  total_con_descuento?: string | null;
  estado: EstadoSolicitudDescuento;
  created_at: string;
  updated_at: string;
}

type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const descuentosApi = {
  crearSolicitud: async (payload: {
    aprobador: number;
    descuento_solicitado: number;
    subtotal?: number;
    iva?: number;
    total_antes_descuento?: number;
    total_con_descuento?: number;
  }) => {
    const response = await apiClient.post<SolicitudDescuento>(
      '/solicitudes-descuento/',
      payload
    );
    return response.data;
  },
  listarSolicitudes: async () => {
    const response = await apiClient.get<
      SolicitudDescuento[] | PaginatedResponse<SolicitudDescuento>
    >('/solicitudes-descuento/');
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return response.data.results ?? [];
  },
  actualizarSolicitud: async (
    id: number,
    payload: Partial<Pick<SolicitudDescuento, 'estado' | 'descuento_aprobado'>>
  ) => {
    const response = await apiClient.patch<SolicitudDescuento>(
      `/solicitudes-descuento/${id}/`,
      payload
    );
    return response.data;
  },
};
