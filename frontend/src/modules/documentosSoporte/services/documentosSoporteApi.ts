import apiClient from '../../../api/client';

export type EstadoDian = 'ACEPTADA' | 'RECHAZADA' | 'EN_PROCESO' | 'ERROR' | string;

export interface DocumentoSoporte {
  numero: string;
  proveedor_nombre: string;
  proveedor_documento: string;
  fecha: string;
  total: number;
  estado_dian: EstadoDian;
}

export interface CrearDocumentoSoportePayload {
  proveedor_nombre: string;
  proveedor_documento: string;
  tipo_documento_proveedor: string;
  descripcion: string;
  cantidad: number;
  valor_unitario: number;
  metodo_pago: string;
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
  async getDocumentosSoporte() {
    const response = await apiClient.get<DocumentoSoporte[]>('/documentos-soporte/');
    return response.data;
  },

  async crearDocumentoSoporte(data: CrearDocumentoSoportePayload) {
    const response = await apiClient.post<DocumentoSoporte>('/documentos-soporte/', data);
    return response.data;
  },

  async descargarXML(numero: string) {
    const response = await apiClient.get<Blob>(`/documentos-soporte/${encodeURIComponent(numero)}/xml/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `documento-soporte-${encodeURIComponent(numero)}.xml`);
  },

  async descargarPDF(numero: string) {
    const response = await apiClient.get<Blob>(`/documentos-soporte/${encodeURIComponent(numero)}/pdf/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `documento-soporte-${encodeURIComponent(numero)}.pdf`);
  },
};
