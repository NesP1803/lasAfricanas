import apiClient from './client';
import type {
  ConfiguracionEmpresa,
  ConfiguracionFacturacion,
  Impuesto,
  AuditoriaRegistro,
  UsuarioAdmin,
  PaginatedResponse,
  AuditoriaRetention,
} from '../types';

const sessionCache = {
  empresa: null as ConfiguracionEmpresa | null,
  facturacion: null as ConfiguracionFacturacion | null,
  usuarioActual: null as UsuarioAdmin | null,
};

const inFlightRequests = {
  empresa: null as Promise<ConfiguracionEmpresa> | null,
  facturacion: null as Promise<ConfiguracionFacturacion> | null,
  usuarioActual: null as Promise<UsuarioAdmin> | null,
};
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
  obtenerEmpresa: async (options?: { force?: boolean }) => {
    if (sessionCache.empresa && !options?.force) {
      return sessionCache.empresa;
    }
    if (inFlightRequests.empresa && !options?.force) {
      return inFlightRequests.empresa;
    }

    inFlightRequests.empresa = apiClient
      .get<ConfiguracionEmpresa[]>('/configuracion-empresa/')
      .then((response) => {
        const empresa = response.data[0];
        sessionCache.empresa = empresa ?? null;
        return empresa;
      })
      .finally(() => {
        inFlightRequests.empresa = null;
      });

    return inFlightRequests.empresa;
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
      sessionCache.empresa = response.data;
      return response.data;
    }

    const response = await apiClient.put<ConfiguracionEmpresa>(
      `/configuracion-empresa/${id}/`,
      data
    );
    sessionCache.empresa = response.data;
    return response.data;
  },
  obtenerFacturacion: async (options?: { force?: boolean }) => {
    if (sessionCache.facturacion && !options?.force) {
      return sessionCache.facturacion;
    }
    if (inFlightRequests.facturacion && !options?.force) {
      return inFlightRequests.facturacion;
    }

    inFlightRequests.facturacion = apiClient
      .get<ConfiguracionFacturacion[]>('/configuracion-facturacion/')
      .then((response) => {
        const facturacion = response.data[0];
        sessionCache.facturacion = facturacion ?? null;
        return facturacion;
      })
      .finally(() => {
        inFlightRequests.facturacion = null;
      });

    return inFlightRequests.facturacion;
  },
  actualizarFacturacion: async (id: number, data: ConfiguracionFacturacion) => {
    const response = await apiClient.put<ConfiguracionFacturacion>(
      `/configuracion-facturacion/${id}/`,
      data
    );
    sessionCache.facturacion = response.data;
    return response.data;
  },
  obtenerRangosFactus: async (documentCode = 'FACTURA_VENTA') => {
    const response = await apiClient.get<{
      environment: 'SANDBOX' | 'PRODUCTION';
      document_code: string;
      selected_range_id: number | null;
      ranges: Array<{
        id: number;
        factus_range_id: number;
        environment: 'SANDBOX' | 'PRODUCTION';
        document_code: string;
        document_name: string;
        prefix: string;
        from_number: number;
        to_number: number;
        current: number;
        resolution_number: string;
        technical_key: string;
        is_active_remote: boolean;
        is_selected_local: boolean;
      }>;
    }>('/factus/rangos/', { params: { document_code: documentCode } });
    return response.data;
  },
  sincronizarRangosFactus: async () => {
    const response = await apiClient.post<{ message: string; count: number }>(
      '/factus/rangos/sincronizar/'
    );
    return response.data;
  },
  seleccionarRangoFactus: async (rangeId: number, documentCode = 'FACTURA_VENTA') => {
    const response = await apiClient.post<{ message: string; range_id: number }>(
      '/factus/rangos/seleccionar-activo/',
      { range_id: rangeId, document_code: documentCode }
    );
    return response.data;
  },
  obtenerImpuestos: async () => {
    const response = await apiClient.get<Impuesto[] | PaginatedResponse<Impuesto>>(
      '/impuestos/'
    );
    if (Array.isArray(response.data)) {
      return response.data;
    }
    if (Array.isArray(response.data?.results)) {
      return response.data.results;
    }
    return [];
  },
  crearImpuesto: async (data: Partial<Impuesto>) => {
    const response = await apiClient.post<Impuesto>('/impuestos/', data);
    return response.data;
  },
  actualizarImpuesto: async (id: number, data: Partial<Impuesto>) => {
    const response = await apiClient.patch<Impuesto>(`/impuestos/${id}/`, data);
    return response.data;
  },
  eliminarImpuesto: async (id: number) => {
    await apiClient.delete(`/impuestos/${id}/`);
  },
  obtenerAuditoria: async (params?: {
    page?: number;
    search?: string;
    fechaInicio?: string;
    fechaFin?: string;
  }) => {
    const response = await apiClient.get<
      PaginatedResponse<AuditoriaRegistro> | AuditoriaRegistro[]
    >('/auditoria/', {
      params: {
        page: params?.page,
        search: params?.search || undefined,
        fecha_hora__gte: params?.fechaInicio || undefined,
        fecha_hora__lte: params?.fechaFin || undefined,
      },
    });
    if (Array.isArray(response.data)) {
      return {
        count: response.data.length,
        next: null,
        previous: null,
        results: response.data,
      };
    }
    return response.data;
  },
  obtenerAuditoriaRetention: async () => {
    const response = await apiClient.get<AuditoriaRetention>(
      '/auditoria/retention/'
    );
    return response.data;
  },
  archivarAuditoria: async (batchSize = 1000) => {
    const response = await apiClient.post<{
      archived: number;
      purged: number;
      total_to_archive: number;
    }>('/auditoria/archivar/', { batch_size: batchSize });
    return response.data;
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
  obtenerAprobadores: async () => {
    const response = await apiClient.get<UsuarioAdmin[]>('/usuarios/aprobadores/');
    return response.data;
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
  obtenerUsuario: async (id: number) => {
    const response = await apiClient.get<UsuarioAdmin>(`/usuarios/${id}/`);
    return response.data;
  },
  obtenerUsuarioActual: async (options?: { force?: boolean }) => {
    if (sessionCache.usuarioActual && !options?.force) {
      return sessionCache.usuarioActual;
    }
    if (inFlightRequests.usuarioActual && !options?.force) {
      return inFlightRequests.usuarioActual;
    }

    inFlightRequests.usuarioActual = apiClient
      .get<UsuarioAdmin>('/usuarios/me/')
      .then((response) => {
        sessionCache.usuarioActual = response.data;
        return response.data;
      })
      .finally(() => {
        inFlightRequests.usuarioActual = null;
      });

    return inFlightRequests.usuarioActual;
  },
  actualizarUsuarioActual: async (data: Partial<UsuarioAdmin>) => {
    const response = await apiClient.patch<UsuarioAdmin>('/usuarios/me/', data);
    sessionCache.usuarioActual = response.data;
    return response.data;
  },
  resetSessionCache: () => {
    sessionCache.empresa = null;
    sessionCache.facturacion = null;
    sessionCache.usuarioActual = null;
    inFlightRequests.empresa = null;
    inFlightRequests.facturacion = null;
    inFlightRequests.usuarioActual = null;
  },
  cambiarClave: async (id: number, newPassword: string) => {
    const response = await apiClient.post<{ detail: string }>(`/usuarios/${id}/change_password/`, {
      new_password: newPassword,
    });
    return response.data;
  },
};
