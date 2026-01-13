import apiClient from './client';
import type { PaginatedResponse, UsuarioAdmin } from '../types';

const API_URL = '/api';

export const usuariosApi = {
  async getUsuarios(params?: { search?: string; page?: number; ordering?: string }): Promise<PaginatedResponse<UsuarioAdmin> | UsuarioAdmin[]> {
    const response = await apiClient.get<PaginatedResponse<UsuarioAdmin> | UsuarioAdmin[]>(
      `${API_URL}/usuarios/`,
      { params }
    );
    return response.data;
  },

  async createUsuario(data: Partial<UsuarioAdmin> & { password?: string }): Promise<UsuarioAdmin> {
    const response = await apiClient.post<UsuarioAdmin>(`${API_URL}/usuarios/`, data);
    return response.data;
  },

  async updateUsuario(id: number, data: Partial<UsuarioAdmin> & { password?: string }): Promise<UsuarioAdmin> {
    const response = await apiClient.patch<UsuarioAdmin>(`${API_URL}/usuarios/${id}/`, data);
    return response.data;
  },

  async deleteUsuario(id: number): Promise<void> {
    await apiClient.delete(`${API_URL}/usuarios/${id}/`);
  },
};
