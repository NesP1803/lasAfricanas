import apiClient from './client';

// Tipos
export interface ConfiguracionEmpresa {
  id?: number;
  tipo_identificacion: string;
  identificacion: string;
  dv: string;
  tipo_persona: string;
  razon_social: string;
  regimen: string;
  direccion: string;
  ciudad: string;
  municipio: string;
  telefono: string;
  sitio_web: string;
  correo: string;
  logo?: string;
}

export interface Impuesto {
  id?: number;
  nombre: string;
  valor: string;
  porcentaje?: number;
  es_exento: boolean;
  is_active: boolean;
}

export interface Auditoria {
  id: number;
  fecha_hora: string;
  usuario: number;
  usuario_nombre: string;
  accion: string;
  modelo: string;
  objeto_id: string;
  notas: string;
  ip_address?: string;
}

export interface Usuario {
  id?: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  nombre_completo?: string;
  tipo_usuario: string;
  telefono: string;
  sede: string;
  is_active: boolean;
  date_joined?: string;
  descuento_maximo: number;
  password?: string;
}

export interface CambiarPassword {
  clave_actual: string;
  clave_nueva: string;
  confirmar_clave: string;
}

export interface Backup {
  nombre: string;
  fecha: string;
  tamaño: number;
}

// API de Configuración de Empresa
export const configuracionEmpresaApi = {
  obtener: async (): Promise<ConfiguracionEmpresa> => {
    const response = await apiClient.get('/config/empresa/');
    return response.data;
  },

  actualizar: async (id: number, data: Partial<ConfiguracionEmpresa>): Promise<ConfiguracionEmpresa> => {
    const response = await apiClient.patch(`/config/empresa/${id}/`, data);
    return response.data;
  },

  subirLogo: async (id: number, file: File): Promise<ConfiguracionEmpresa> => {
    const formData = new FormData();
    formData.append('logo', file);
    const response = await apiClient.patch(`/config/empresa/${id}/`, formData, {
      headers: {'Content-Type': 'multipart/form-data'},
    });
    return response.data;
  },
};

// API de Impuestos
export const impuestosApi = {
  listar: async (): Promise<Impuesto[]> => {
    const response = await apiClient.get('/config/impuestos/');
    return response.data;
  },

  crear: async (data: Partial<Impuesto>): Promise<Impuesto> => {
    const response = await apiClient.post('/config/impuestos/', data);
    return response.data;
  },

  actualizar: async (id: number, data: Partial<Impuesto>): Promise<Impuesto> => {
    const response = await apiClient.patch(`/config/impuestos/${id}/`, data);
    return response.data;
  },

  eliminar: async (id: number): Promise<void> => {
    await apiClient.delete(`/config/impuestos/${id}/`);
  },
};

// API de Auditoría
export const auditoriaApi = {
  listar: async (): Promise<Auditoria[]> => {
    const response = await apiClient.get('/config/auditoria/');
    return response.data;
  },
};

// API de Usuarios
export const usuariosApi = {
  listar: async (): Promise<Usuario[]> => {
    const response = await apiClient.get('/config/usuarios/');
    return response.data;
  },

  crear: async (data: Partial<Usuario>): Promise<Usuario> => {
    const response = await apiClient.post('/config/usuarios/', data);
    return response.data;
  },

  actualizar: async (id: number, data: Partial<Usuario>): Promise<Usuario> => {
    const response = await apiClient.patch(`/config/usuarios/${id}/`, data);
    return response.data;
  },

  desactivar: async (id: number): Promise<void> => {
    await apiClient.post(`/config/usuarios/${id}/desactivar/`);
  },

  cambiarPassword: async (data: CambiarPassword): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/config/usuarios/cambiar_password/', data);
    return response.data;
  },
};

// API de Backup
export const backupApi = {
  crearBackup: async (): Promise<{ status: string; message: string; archivo: string }> => {
    const response = await apiClient.post('/config/backup/crear_backup/');
    return response.data;
  },

  listarBackups: async (): Promise<Backup[]> => {
    const response = await apiClient.get('/config/backup/listar_backups/');
    return response.data;
  },
};
