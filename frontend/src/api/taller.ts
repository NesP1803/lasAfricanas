import type { PaginatedResponse } from '../types';

const API_URL = '/api';

export interface Mecanico {
  id: number;
  nombre: string;
  telefono?: string;
  email?: string;
  direccion?: string;
  ciudad?: string;
  is_active: boolean;
}

export interface Moto {
  id: number;
  placa: string;
  marca: string;
  modelo?: string;
  color?: string;
  anio?: number | null;
  cliente?: number | null;
  cliente_nombre?: string;
  mecanico?: number | null;
  mecanico_nombre?: string;
  proveedor?: number | null;
  proveedor_nombre?: string;
  observaciones?: string;
  is_active: boolean;
}

export interface OrdenRepuesto {
  id: number;
  orden: number;
  producto: number;
  producto_codigo?: string;
  producto_nombre?: string;
  cantidad: number;
  precio_unitario: string;
  subtotal: string;
  iva_porcentaje?: string;
}

export interface OrdenTaller {
  id: number;
  moto: number;
  moto_placa?: string;
  moto_marca?: string;
  moto_modelo?: string;
  mecanico: number;
  mecanico_nombre?: string;
  estado: 'EN_PROCESO' | 'LISTO_FACTURAR' | 'FACTURADO';
  observaciones?: string;
  fecha_entrega?: string | null;
  venta?: number | null;
  venta_numero?: string | null;
  repuestos: OrdenRepuesto[];
  total: string;
}

const getToken = () => localStorage.getItem('token');

export const tallerApi = {
  async getMecanicos(params?: { search?: string; page?: number }): Promise<PaginatedResponse<Mecanico> | Mecanico[]> {
    const token = getToken();
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/mecanicos/${query ? `?${query}` : ''}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener mecánicos');
    return response.json();
  },

  async createMecanico(data: Partial<Mecanico>): Promise<Mecanico> {
    const token = getToken();
    const response = await fetch(`${API_URL}/mecanicos/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async updateMecanico(id: number, data: Partial<Mecanico>): Promise<Mecanico> {
    const token = getToken();
    const response = await fetch(`${API_URL}/mecanicos/${id}/`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async deleteMecanico(id: number): Promise<void> {
    const token = getToken();
    const response = await fetch(`${API_URL}/mecanicos/${id}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) throw new Error('Error al eliminar mecánico');
  },

  async getMotos(params?: { search?: string; page?: number; mecanico?: number }): Promise<PaginatedResponse<Moto> | Moto[]> {
    const token = getToken();
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.mecanico) queryParams.append('mecanico', params.mecanico.toString());
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/motos/${query ? `?${query}` : ''}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener motos');
    return response.json();
  },

  async createMoto(data: Partial<Moto>): Promise<Moto> {
    const token = getToken();
    const response = await fetch(`${API_URL}/motos/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async updateMoto(id: number, data: Partial<Moto>): Promise<Moto> {
    const token = getToken();
    const response = await fetch(`${API_URL}/motos/${id}/`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async deleteMoto(id: number): Promise<void> {
    const token = getToken();
    const response = await fetch(`${API_URL}/motos/${id}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) throw new Error('Error al eliminar moto');
  },

  async getOrdenes(params?: { search?: string; page?: number; moto?: number; mecanico?: number; estado?: string }): Promise<PaginatedResponse<OrdenTaller> | OrdenTaller[]> {
    const token = getToken();
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.moto) queryParams.append('moto', params.moto.toString());
    if (params?.mecanico) queryParams.append('mecanico', params.mecanico.toString());
    if (params?.estado) queryParams.append('estado', params.estado);
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/ordenes-taller/${query ? `?${query}` : ''}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener órdenes');
    return response.json();
  },

  async createOrden(data: Partial<OrdenTaller>): Promise<OrdenTaller> {
    const token = getToken();
    const response = await fetch(`${API_URL}/ordenes-taller/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async updateOrden(id: number, data: Partial<OrdenTaller>): Promise<OrdenTaller> {
    const token = getToken();
    const response = await fetch(`${API_URL}/ordenes-taller/${id}/`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async deleteOrden(id: number): Promise<void> {
    const token = getToken();
    const response = await fetch(`${API_URL}/ordenes-taller/${id}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) throw new Error('Error al eliminar orden');
  },

  async agregarRepuesto(ordenId: number, payload: { producto: number; cantidad: number }): Promise<OrdenTaller> {
    const token = getToken();
    const response = await fetch(`${API_URL}/ordenes-taller/${ordenId}/agregar_repuesto/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Error al agregar repuesto');
    }
    return response.json();
  },

  async quitarRepuesto(ordenId: number, payload: { repuesto_id?: number; producto?: number }): Promise<OrdenTaller> {
    const token = getToken();
    const response = await fetch(`${API_URL}/ordenes-taller/${ordenId}/quitar_repuesto/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Error al quitar repuesto');
    }
    return response.json();
  },

  async facturarOrden(ordenId: number, payload?: { tipo_comprobante?: 'REMISION' | 'FACTURA' }): Promise<OrdenTaller> {
    const token = getToken();
    const response = await fetch(`${API_URL}/ordenes-taller/${ordenId}/facturar/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload ?? {}),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Error al facturar');
    }
    return response.json();
  },
};
