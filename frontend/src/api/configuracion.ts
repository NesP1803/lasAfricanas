import apiClient from './client';
import type {
  ConfiguracionEmpresa,
  ConfiguracionFacturacion,
  Impuesto,
  AuditoriaRegistro,
  UsuarioAdmin,
  PaginatedResponse,
} from '../types';

const buildEmpresaFormData = (
  data: ConfiguracionEmpresa,
  logoFile?: File | null,
  removeLogo?: boolean
) => {
  const formData = new FormData();
  Object.entries(data).forEach(([key, value]) => {
    if (key === 'logo') {
      return;
    }
    formData.append(key, value === null ? '' : String(value));
  });

  if (logoFile) {
    formData.append('logo', logoFile);
  } else if (removeLogo) {
    formData.append('logo', '');
  }

  return formData;
};

export const configuracionAPI = {
  obtenerEmpresa: async () => {
    const response = await apiClient.get<ConfiguracionEmpresa[]>(
      '/configuracion-empresa/'
    );
    return response.data[0];
  },
  actualizarEmpresa: async (
    id: number,
    data: ConfiguracionEmpresa,
    options?: { logoFile?: File | null; removeLogo?: boolean }
  ) => {
    if (options?.logoFile || options?.removeLogo) {
      const formData = buildEmpresaFormData(
        data,
        options?.logoFile,
        options?.removeLogo
      );
      const response = await apiClient.put<ConfiguracionEmpresa>(
        `/configuracion-empresa/${id}/`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data;
    }

    const response = await apiClient.put<ConfiguracionEmpresa>(
      `/configuracion-empresa/${id}/`,
      data
    );
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
    const response = await apiClient.get<
      UsuarioAdmin[] | PaginatedResponse<UsuarioAdmin>
    >('/usuarios/');
    if (Array.isArray(response.data)) {
      return response.data;
    }
    if (Array.isArray(response.data.results)) {
      return response.data.results;
    }
    return [];
  },
  actualizarUsuario: async (id: number, data: Partial<UsuarioAdmin>) => {
    const response = await apiClient.patch<UsuarioAdmin>(
      `/usuarios/${id}/`,
      data
    );
    return response.data;
  },
  cambiarClave: async (id: number, newPassword: string) => {
    const response = await apiClient.post<{ detail: string }>(`/usuarios/${id}/change_password/`, {
      new_password: newPassword,
    });
    return response.data;
  },
};
