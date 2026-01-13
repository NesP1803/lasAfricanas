import apiClient from './client';
import type {
  ConfiguracionEmpresa,
  ConfiguracionFacturacion,
  Impuesto,
  AuditoriaRegistro,
  UsuarioAdmin,
  PaginatedResponse,
} from '../types';

export const configuracionAPI = {
  obtenerEmpresa: async () => {
    const response = await apiClient.get<ConfiguracionEmpresa[]>('/configuracion-empresa/');
    return response.data[0];
  },
  actualizarEmpresa: async (id: number, data: ConfiguracionEmpresa) => {
    const response = await apiClient.put<ConfiguracionEmpresa>(`/configuracion-empresa/${id}/`, data);
    return response.data;
  },
  obtenerFacturacion: async () => {
    const response = await apiClient.get<ConfiguracionFacturacion[]>('/configuracion-facturacion/');
    return response.data[0];
  },
  actualizarFacturacion: async (id: number, data: ConfiguracionFacturacion) => {
    const response = await apiClient.put<ConfiguracionFacturacion>(
      `/configuracion-facturacion/${id}/`,
      data
    );
    return response.data;
  },
  obtenerImpuestos: async () => {
    const response = await apiClient.get<Impuesto[]>('/impuestos/');
    return response.data;
  },
  crearImpuesto: async (data: Partial<Impuesto>) => {
    const response = await apiClient.post<Impuesto>('/impuestos/', data);
    return response.data;
  },
  eliminarImpuesto: async (id: number) => {
    await apiClient.delete(`/impuestos/${id}/`);
  },
  obtenerAuditoria: async () => {
    const response = await apiClient.get<PaginatedResponse<AuditoriaRegistro> | AuditoriaRegistro[]>(
      '/auditoria/'
    );
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return response.data.results;
  },
  obtenerUsuarios: async () => {
    const response = await apiClient.get<UsuarioAdmin[]>('/usuarios/');
    return response.data;
  },
  actualizarUsuario: async (id: number, data: Partial<UsuarioAdmin>) => {
    const response = await apiClient.put<UsuarioAdmin>(`/usuarios/${id}/`, data);
    return response.data;
  },
  cambiarClave: async (id: number, newPassword: string) => {
    const response = await apiClient.post<{ detail: string }>(`/usuarios/${id}/change_password/`, {
      new_password: newPassword,
    });
    return response.data;
  },
};
