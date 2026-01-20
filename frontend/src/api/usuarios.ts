import type { PaginatedResponse, UsuarioAdmin } from '../types';

export interface DescuentoApprovalPayload {
  username: string;
  password: string;
  descuento_porcentaje: number;
}

export interface DescuentoApprovalResponse {
  id: number;
  nombre: string;
  descuento_maximo?: string | null;
}

const API_URL = '/api';

export const usuariosApi = {
  async getUsuarios(
    params?: {
      search?: string;
      page?: number;
      ordering?: string;
      is_active?: boolean;
      tipo_usuario?: string;
      sede?: string;
    }
  ): Promise<PaginatedResponse<UsuarioAdmin> | UsuarioAdmin[]> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.ordering) queryParams.append('ordering', params.ordering);
    if (params?.is_active !== undefined) queryParams.append('is_active', String(params.is_active));
    if (params?.tipo_usuario) queryParams.append('tipo_usuario', params.tipo_usuario);
    if (params?.sede) queryParams.append('sede', params.sede);
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/usuarios/${query ? `?${query}` : ''}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Error al obtener usuarios');
    }
    return response.json();
  },
  async validarDescuento(payload: DescuentoApprovalPayload): Promise<DescuentoApprovalResponse> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/usuarios/validar_descuento/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'No se pudo validar el descuento');
    }

    return response.json();
  },
  async createUsuario(data: Partial<UsuarioAdmin>): Promise<UsuarioAdmin> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/usuarios/`, {
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
  async updateUsuario(id: number, data: Partial<UsuarioAdmin>): Promise<UsuarioAdmin> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/usuarios/${id}/`, {
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
  async deleteUsuario(id: number): Promise<void> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/usuarios/${id}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Error al eliminar usuario');
    }
  },
};
