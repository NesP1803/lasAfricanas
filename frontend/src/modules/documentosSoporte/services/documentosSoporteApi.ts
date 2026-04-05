import apiClient from '../../../api/client';

export type EstadoDian = 'ACEPTADA' | 'RECHAZADA' | 'EN_PROCESO' | 'ERROR' | string;

export interface DocumentoSoporte {
  id: number;
  numero: string;
  proveedor_nombre: string;
  proveedor_documento: string;
  proveedor_tipo_documento: string;
  fecha: string;
  total: number;
  estado?: EstadoDian;
  estado_dian: EstadoDian;
  cufe?: string;
  uuid?: string;
  xml_url?: string;
  pdf_url?: string;
  reference_code?: string;
  can_sync?: boolean;
}

export interface CrearDocumentoSoportePayload {
  proveedor_nombre: string;
  proveedor_documento: string;
  proveedor_tipo_documento: string;
  proveedor_id?: number;
  provider_address?: string;
  provider_email?: string;
  provider_phone?: string;
  provider_country_code?: string;
  provider_municipality_id?: number;
  observation?: string;
  items: Array<{
    descripcion: string;
    cantidad: number;
    precio: number;
  }>;
}

export interface ProveedorSugerencia {
  id: number;
  nombre: string;
  nit?: string;
  direccion?: string;
  email?: string;
  telefono?: string;
  ciudad?: string;
}

const crearArchivoDescargable = (blob: Blob, fileName: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.target = '_blank';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const documentosSoporteApi = {
  async buscarProveedores(search: string) {
    const response = await apiClient.get<{ results?: ProveedorSugerencia[] } | ProveedorSugerencia[]>(
      '/proveedores/',
      {
        params: { is_active: true, search, page_size: 20 },
      },
    );
    const payload = response.data;
    return Array.isArray(payload) ? payload : (payload.results ?? []);
  },

  async getDocumentosSoporte() {
    const response = await apiClient.get<DocumentoSoporte[]>('/documentos-soporte/');
    return response.data;
  },

  async crearDocumentoSoporte(data: CrearDocumentoSoportePayload) {
    const response = await apiClient.post<DocumentoSoporte>('/documentos-soporte/', data);
    return response.data;
  },

  async descargarXML(id: number, numero: string) {
    const response = await apiClient.get<Blob>(`/documentos-soporte/${id}/xml/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `documento-soporte-${encodeURIComponent(numero)}.xml`);
  },

  async descargarPDF(id: number, numero: string) {
    const response = await apiClient.get<Blob>(`/documentos-soporte/${id}/pdf/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `documento-soporte-${encodeURIComponent(numero)}.pdf`);
  },

  async getDocumentoSoporte(id: number) {
    const response = await apiClient.get<DocumentoSoporte>(`/documentos-soporte/${id}/`);
    return response.data;
  },

  async sincronizarDocumentoSoporte(id: number) {
    const response = await apiClient.post<DocumentoSoporte>(`/documentos-soporte/${id}/sincronizar/`);
    return response.data;
  },

  async estadoRemotoDocumentoSoporte(id: number) {
    const response = await apiClient.get(`/documentos-soporte/${id}/estado-remoto/`);
    return response.data;
  },

  async eliminarDocumentoSoporte(id: number) {
    const response = await apiClient.delete(`/documentos-soporte/${id}/`);
    return response.data;
  },
};
