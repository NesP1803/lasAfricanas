import apiClient from './client';
import type {
  Mecanico,
  ServicioMotoList,
  ServicioMotoDetalle,
  ServicioMotoCreate,
  RepuestoAsignado,
  ConsumoRepuesto,
  EstadisticasTaller,
  PaginatedResponse,
  EstadoServicio,
  ServicioMotoUpdate,
  Venta
} from '../types';

const API_URL = '/api';

// ============================================
// MECÁNICOS
// ============================================
export const mecanicoAPI = {
  // Obtener todos los mecánicos
  getAll: async (params?: { search?: string; page?: number; ordering?: string }): Promise<PaginatedResponse<Mecanico>> => {
    const response = await apiClient.get(`${API_URL}/mecanicos/`, { params });
    return response.data;
  },

  // Obtener un mecánico por ID
  getById: async (id: number): Promise<Mecanico> => {
    const response = await apiClient.get(`${API_URL}/mecanicos/${id}/`);
    return response.data;
  },

  // Crear mecánico
  create: async (data: Partial<Mecanico>): Promise<Mecanico> => {
    const response = await apiClient.post(`${API_URL}/mecanicos/`, data);
    return response.data;
  },

  // Actualizar mecánico
  update: async (id: number, data: Partial<Mecanico>): Promise<Mecanico> => {
    const response = await apiClient.patch(`${API_URL}/mecanicos/${id}/`, data);
    return response.data;
  },

  // Eliminar mecánico (soft delete)
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${API_URL}/mecanicos/${id}/`);
  },

  // Obtener repuestos asignados a un mecánico
  getRepuestos: async (id: number): Promise<RepuestoAsignado[]> => {
    const response = await apiClient.get(`${API_URL}/mecanicos/${id}/repuestos/`);
    return response.data;
  },

  // Obtener servicios activos de un mecánico
  getServiciosActivos: async (id: number): Promise<ServicioMotoList[]> => {
    const response = await apiClient.get(`${API_URL}/mecanicos/${id}/servicios_activos/`);
    return response.data;
  }
};

// ============================================
// SERVICIOS DE MOTOS
// ============================================
export const servicioAPI = {
  // Obtener todos los servicios
  getAll: async (params?: {
    estado?: EstadoServicio;
    mecanico?: number;
    cliente?: number;
    search?: string;
    ordering?: string;
    page?: number;
  }): Promise<PaginatedResponse<ServicioMotoList>> => {
    const response = await apiClient.get(`${API_URL}/servicios/`, { params });
    return response.data;
  },

  // Obtener un servicio por ID
  getById: async (id: number): Promise<ServicioMotoDetalle> => {
    const response = await apiClient.get(`${API_URL}/servicios/${id}/`);
    return response.data;
  },

  // Crear nuevo servicio
  create: async (data: ServicioMotoCreate): Promise<ServicioMotoDetalle> => {
    const response = await apiClient.post(`${API_URL}/servicios/`, data);
    return response.data;
  },

  // Actualizar servicio
  update: async (
    id: number,
    data: ServicioMotoUpdate
  ): Promise<ServicioMotoDetalle> => {
    const response = await apiClient.patch(`${API_URL}/servicios/${id}/`, data);
    return response.data;
  },

  // Eliminar servicio
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${API_URL}/servicios/${id}/`);
  },

  // Buscar servicios por placa
  buscarPorPlaca: async (placa: string): Promise<ServicioMotoList[]> => {
    const response = await apiClient.get(`${API_URL}/servicios/buscar_por_placa/`, {
      params: { placa }
    });
    return response.data;
  },

  // Obtener historial completo de servicios por placa
  historialPorPlaca: async (placa: string): Promise<ServicioMotoDetalle[]> => {
    const response = await apiClient.get(`${API_URL}/servicios/historial_por_placa/`, {
      params: { placa }
    });
    return response.data;
  },

  // Obtener servicios por mecánico
  porMecanico: async (
    mecanicoId: number,
    estado?: EstadoServicio
  ): Promise<ServicioMotoList[]> => {
    const response = await apiClient.get(`${API_URL}/servicios/por_mecanico/`, {
      params: { mecanico_id: mecanicoId, estado }
    });
    return response.data;
  },

  // Agregar repuesto al servicio
  agregarRepuesto: async (
    id: number,
    data: {
      producto_id: number;
      cantidad: number;
      precio_unitario: string;
      descuento?: string;
    }
  ): Promise<ConsumoRepuesto> => {
    const response = await apiClient.post(
      `${API_URL}/servicios/${id}/agregar_repuesto/`,
      data
    );
    return response.data;
  },

  // Cambiar estado del servicio
  cambiarEstado: async (
    id: number,
    nuevoEstado: EstadoServicio,
    observaciones?: string
  ): Promise<ServicioMotoDetalle> => {
    const response = await apiClient.post(`${API_URL}/servicios/${id}/cambiar_estado/`, {
      nuevo_estado: nuevoEstado,
      observaciones
    });
    return response.data;
  },

  // Facturar servicio
  facturar: async (
    id: number,
    data: {
      tipo_comprobante?: 'FACTURA' | 'REMISION';
      medio_pago?: 'EFECTIVO' | 'TRANSFERENCIA' | 'TARJETA' | 'CREDITO';
      efectivo_recibido?: string;
    }
  ): Promise<Venta> => {
    const response = await apiClient.post(`${API_URL}/servicios/${id}/facturar/`, data);
    return response.data;
  },

  // Obtener estadísticas del taller
  getEstadisticas: async (): Promise<EstadisticasTaller> => {
    const response = await apiClient.get(`${API_URL}/servicios/estadisticas/`);
    return response.data;
  }
};

// ============================================
// REPUESTOS ASIGNADOS
// ============================================
export const repuestoAsignadoAPI = {
  // Obtener todos los repuestos asignados
  getAll: async (params?: {
    mecanico?: number;
    search?: string;
  }): Promise<PaginatedResponse<RepuestoAsignado>> => {
    const response = await apiClient.get(`${API_URL}/repuestos-asignados/`, { params });
    return response.data;
  },

  // Obtener un repuesto asignado por ID
  getById: async (id: number): Promise<RepuestoAsignado> => {
    const response = await apiClient.get(`${API_URL}/repuestos-asignados/${id}/`);
    return response.data;
  },

  // Crear asignación de repuesto
  create: async (data: {
    mecanico: number;
    producto: number;
    cantidad: number;
    precio_unitario: string;
  }): Promise<RepuestoAsignado> => {
    const response = await apiClient.post(`${API_URL}/repuestos-asignados/`, data);
    return response.data;
  },

  // Actualizar repuesto asignado
  update: async (
    id: number,
    data: Partial<RepuestoAsignado>
  ): Promise<RepuestoAsignado> => {
    const response = await apiClient.patch(`${API_URL}/repuestos-asignados/${id}/`, data);
    return response.data;
  },

  // Eliminar repuesto asignado
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${API_URL}/repuestos-asignados/${id}/`);
  }
};

// ============================================
// CONSUMOS DE REPUESTOS
// ============================================
export const consumoRepuestoAPI = {
  // Obtener todos los consumos
  getAll: async (params?: {
    servicio?: number;
    descontado_de_mecanico?: boolean;
    search?: string;
  }): Promise<PaginatedResponse<ConsumoRepuesto>> => {
    const response = await apiClient.get(`${API_URL}/consumos/`, { params });
    return response.data;
  },

  // Obtener un consumo por ID
  getById: async (id: number): Promise<ConsumoRepuesto> => {
    const response = await apiClient.get(`${API_URL}/consumos/${id}/`);
    return response.data;
  }
};

// ============================================
// UTILIDADES
// ============================================

// Colores para los estados de servicio
export const estadoColors: Record<EstadoServicio, string> = {
  INGRESADO: 'bg-blue-100 text-blue-800',
  EN_DIAGNOSTICO: 'bg-yellow-100 text-yellow-800',
  COTIZADO: 'bg-purple-100 text-purple-800',
  APROBADO: 'bg-indigo-100 text-indigo-800',
  EN_REPARACION: 'bg-orange-100 text-orange-800',
  TERMINADO: 'bg-green-100 text-green-800',
  ENTREGADO: 'bg-gray-100 text-gray-800',
  CANCELADO: 'bg-red-100 text-red-800'
};

// Nombres legibles para los estados
export const estadoNames: Record<EstadoServicio, string> = {
  INGRESADO: 'Ingresado',
  EN_DIAGNOSTICO: 'En Diagnóstico',
  COTIZADO: 'Cotizado',
  APROBADO: 'Aprobado',
  EN_REPARACION: 'En Reparación',
  TERMINADO: 'Terminado',
  ENTREGADO: 'Entregado',
  CANCELADO: 'Cancelado'
};

// Validar transición de estado
export const puedeTransicionar = (
  estadoActual: EstadoServicio,
  nuevoEstado: EstadoServicio
): boolean => {
  const transiciones: Record<EstadoServicio, EstadoServicio[]> = {
    INGRESADO: ['EN_DIAGNOSTICO', 'CANCELADO'],
    EN_DIAGNOSTICO: ['COTIZADO', 'CANCELADO'],
    COTIZADO: ['APROBADO', 'CANCELADO'],
    APROBADO: ['EN_REPARACION', 'CANCELADO'],
    EN_REPARACION: ['TERMINADO', 'CANCELADO'],
    TERMINADO: ['ENTREGADO', 'EN_REPARACION'],
    ENTREGADO: [],
    CANCELADO: []
  };

  return transiciones[estadoActual]?.includes(nuevoEstado) || false;
};

// Formatear moneda
export const formatCurrency = (value: string | number): string => {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(num);
};

// Formatear fecha
export const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('es-CO', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const formatDateShort = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('es-CO', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
};
