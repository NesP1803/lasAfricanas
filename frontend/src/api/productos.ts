import apiClient from './client';
import type { Producto, PaginatedResponse } from '../types';

export const productosApi = {
  // Listar productos
  getAll: async (params?: {
    search?: string;
    categoria?: number;
    page?: number;
  }): Promise<PaginatedResponse<Producto>> => {
    const response = await apiClient.get<PaginatedResponse<Producto>>('/productos/', {
      params,
    });
    return response.data;
  },

  // Buscar por código
  buscarPorCodigo: async (codigo: string): Promise<Producto> => {
    const response = await apiClient.get<Producto>('/productos/buscar_por_codigo/', {
      params: { codigo },
    });
    return response.data;
  },

  // Obtener uno
  getById: async (id: number): Promise<Producto> => {
    const response = await apiClient.get<Producto>(`/productos/${id}/`);
    return response.data;
  },

  // Crear
  create: async (data: Partial<Producto>): Promise<Producto> => {
    const response = await apiClient.post<Producto>('/productos/', data);
    return response.data;
  },

  // Actualizar
  update: async (id: number, data: Partial<Producto>): Promise<Producto> => {
    const response = await apiClient.put<Producto>(`/productos/${id}/`, data);
    return response.data;
  },

  // Stock bajo
  stockBajo: async (): Promise<Producto[]> => {
    const response = await apiClient.get<Producto[]>('/productos/stock_bajo/');
    return response.data;
  },
};