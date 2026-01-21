import apiClient from './client';
import type {
  ConfiguracionEmpresa,
  ConfiguracionFacturacion,
  Impuesto,
  AuditoriaRegistro,
  UsuarioAdmin,
  PaginatedResponse,
} from '../types';
import type { ModuleAccess } from '../store/moduleAccess';

type ConfiguracionModulosResponse = {
  id: number;
  configuracion: number;
  configuracion_enabled: boolean;
  registrar_enabled: boolean;
  listados_enabled: boolean;
  articulos_enabled: boolean;
  taller_enabled: boolean;
  facturacion_enabled: boolean;
  reportes_enabled: boolean;
};

const mapModulosToAccess = (
  data: ConfiguracionModulosResponse
): ModuleAccess => ({
  configuracion: data.configuracion_enabled,
  registrar: data.registrar_enabled,
  listados: data.listados_enabled,
  articulos: data.articulos_enabled,
  taller: data.taller_enabled,
  facturacion: data.facturacion_enabled,
  reportes: data.reportes_enabled,
});

const mapAccessToPayload = (data: ModuleAccess) => ({
  configuracion_enabled: data.configuracion,
  registrar_enabled: data.registrar,
  listados_enabled: data.listados,
  articulos_enabled: data.articulos,
  taller_enabled: data.taller,
  facturacion_enabled: data.facturacion,
  reportes_enabled: data.reportes,
});

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
  crearUsuario: async (data: Partial<UsuarioAdmin> & { password?: string }) => {
    const response = await apiClient.post<UsuarioAdmin>('/usuarios/', data);
    return response.data;
  },
  actualizarUsuario: async (id: number, data: Partial<UsuarioAdmin>) => {
    const response = await apiClient.patch<UsuarioAdmin>(
      `/usuarios/${id}/`,
      data
    );
    return response.data;
  },
  obtenerUsuarioActual: async () => {
    const response = await apiClient.get<UsuarioAdmin>('/usuarios/me/');
    return response.data;
  },
  actualizarUsuarioActual: async (data: Partial<UsuarioAdmin>) => {
    const response = await apiClient.patch<UsuarioAdmin>('/usuarios/me/', data);
    return response.data;
  },
  obtenerAccesosModulos: async () => {
    const response = await apiClient.get<ConfiguracionModulosResponse[]>(
      '/configuracion-modulos/'
    );
    const data = response.data[0];
    if (!data) {
      throw new Error('No se encontró configuración de módulos.');
    }
    return { id: data.id, access: mapModulosToAccess(data) };
  },
  actualizarAccesosModulos: async (id: number, data: ModuleAccess) => {
    const response = await apiClient.patch<ConfiguracionModulosResponse>(
      `/configuracion-modulos/${id}/`,
      mapAccessToPayload(data)
    );
    return { id: response.data.id, access: mapModulosToAccess(response.data) };
  },
  cambiarClave: async (id: number, newPassword: string) => {
    const response = await apiClient.post<{ detail: string }>(`/usuarios/${id}/change_password/`, {
      new_password: newPassword,
    });
    return response.data;
  },
};
