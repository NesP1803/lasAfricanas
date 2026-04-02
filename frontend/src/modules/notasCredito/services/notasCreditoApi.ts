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
  motivo: string;
  lines: Array<{
    detalle_venta_original_id: number;
    cantidad_a_acreditar: number;
    afecta_inventario: boolean;
    motivo_linea?: string;
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

  async previewNotaCredito(facturaId: number, data: CrearNotaCreditoPayload) {
    const response = await apiClient.post(`/facturacion/facturas/${facturaId}/notas-credito/preview/`, data);
    return response.data;
  },

  async crearNotaCreditoParcial(facturaId: number, data: CrearNotaCreditoPayload) {
    const response = await apiClient.post<NotaCredito>(`/facturacion/facturas/${facturaId}/notas-credito/parcial/`, data);
    return response.data;
  },

  async crearNotaCreditoTotal(facturaId: number, motivo: string, afecta_inventario = true) {
    const response = await apiClient.post<NotaCredito>(`/facturacion/facturas/${facturaId}/notas-credito/total/`, {
      motivo,
      afecta_inventario,
    });
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

  async getNotaCredito(id: number) {
    const response = await apiClient.get<NotaCredito>(`/notas-credito/${id}/`);
    return response.data;
  },

  async sincronizarNotaCredito(id: number) {
    const response = await apiClient.post(`/notas-credito/${id}/sincronizar/`);
    return response.data;
  },

  async obtenerContenidoCorreo(id: number) {
    const response = await apiClient.get(`/notas-credito/${id}/correo/contenido/`);
    return response.data;
  },

  async enviarCorreo(id: number, email?: string) {
    const response = await apiClient.post(`/notas-credito/${id}/enviar-correo/`, email ? { email } : {});
    return response.data;
  },

  async eliminarNotaCredito(id: number) {
    const response = await apiClient.post(`/notas-credito/${id}/eliminar/`);
    return response.data;
  },
};
