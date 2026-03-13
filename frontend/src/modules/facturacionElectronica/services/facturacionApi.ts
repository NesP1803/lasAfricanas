import apiClient from '../../../api/client';

export type EstadoDian = 'ACEPTADA' | 'RECHAZADA' | 'EN_PROCESO' | 'ERROR' | string;

export interface FacturaElectronica {
  numero: string;
  cliente: string;
  fecha: string;
  total: number;
  estado_dian: EstadoDian;
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

export const facturacionApi = {
  async getFacturas() {
    const response = await apiClient.get<FacturaElectronica[]>('/facturacion/');
    return response.data;
  },

  async getEstadoFactura(numero: string) {
    const response = await apiClient.get<{ estado: EstadoDian }>(`/facturacion/${encodeURIComponent(numero)}/estado/`);
    return response.data;
  },

  async descargarXML(numero: string) {
    const response = await apiClient.get<Blob>(`/facturacion/${encodeURIComponent(numero)}/xml/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `factura-${encodeURIComponent(numero)}.xml`);
  },

  async descargarPDF(numero: string) {
    const response = await apiClient.get<Blob>(`/facturacion/${encodeURIComponent(numero)}/pdf/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `factura-${encodeURIComponent(numero)}.pdf`);
  },

  async enviarFacturaCorreo(numero: string) {
    const response = await apiClient.post(`/facturacion/${encodeURIComponent(numero)}/enviar-correo/`);
    return response.data;
  },
};
