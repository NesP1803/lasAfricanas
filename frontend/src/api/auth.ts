import apiClient, { clearAuthStorage } from './client';
import type { ModulosPermitidos } from '../types';

interface AuthLoginResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    username: string;
    role: string;
    email?: string;
    es_cajero?: boolean;
    modulos_permitidos?: ModulosPermitidos | null;
  };
}

export const authApi = {
  // Login
  login: async (username: string, password: string): Promise<AuthLoginResponse> => {
    const response = await apiClient.post<AuthLoginResponse>('/auth/login/', {
      username,
      password,
    });
    return response.data;
  },

  // Refresh token
  refresh: async (refreshToken: string): Promise<{ access: string }> => {
    const response = await apiClient.post('/auth/refresh/', {
      refresh: refreshToken,
    });
    return response.data;
  },

  // Logout (limpiar tokens locales)
  logout: () => {
    clearAuthStorage();
    localStorage.removeItem('user');
  },
};
