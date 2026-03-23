import apiClient from '../../../api/client';

export type EstadoDian = 'ACEPTADA' | 'RECHAZADA' | 'EN_PROCESO' | 'ERROR' | string;

export interface NotaCredito {
  id: number;
  numero: string;
  factura_asociada: string;
  fecha: string;
  motivo: string;
  estado?: EstadoDian;
  estado_dian: EstadoDian;
  cufe?: string;
  uuid?: string;
  xml_url?: string;
  pdf_url?: string;
}

export interface CrearNotaCreditoPayload {
  factura_id: number;
  motivo: string;
  items: Array<{
    descripcion: string;
    cantidad: number;
    precio: number;
  }>;
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

export const notasCreditoApi = {
  async getNotasCredito() {
    const response = await apiClient.get<NotaCredito[]>('/notas-credito/');
    return response.data;
  },

  async crearNotaCredito(data: CrearNotaCreditoPayload) {
    const response = await apiClient.post<NotaCredito>('/notas-credito/', data);
    return response.data;
  },

  async descargarXML(numero: string) {
    const response = await apiClient.get<Blob>(`/notas-credito/${encodeURIComponent(numero)}/xml/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `nota-credito-${encodeURIComponent(numero)}.xml`);
  },

  async descargarPDF(numero: string) {
    const response = await apiClient.get<Blob>(`/notas-credito/${encodeURIComponent(numero)}/pdf/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `nota-credito-${encodeURIComponent(numero)}.pdf`);
  },
};
