import apiClient from './client';
import type { LoginResponse } from '../types';

export const authApi = {
  // Login
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/auth/login/', {
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
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  },
};