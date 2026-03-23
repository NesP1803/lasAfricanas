import apiClient from '../../../api/client';

export type EstadoDian = 'ACEPTADA' | 'RECHAZADA' | 'EN_PROCESO' | 'ERROR' | string;

export interface FacturaElectronica {
  venta_id?: number;
  numero: string;
  reference_code?: string;
  cufe?: string;
  uuid?: string;
  cliente: string;
  fecha: string;
  total: number;
  estado?: EstadoDian;
  estado_dian: EstadoDian;
  status?: EstadoDian;
  xml_url?: string;
  pdf_url?: string;
}

interface EstadoFacturaResponse {
  estado?: EstadoDian;
  estado_dian?: EstadoDian;
  status?: EstadoDian;
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
    const response = await apiClient.get<EstadoFacturaResponse>(`/facturacion/${encodeURIComponent(numero)}/estado/`);
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

export const resolveEstadoFactura = (data?: EstadoFacturaResponse | FacturaElectronica): EstadoDian => {
  if (!data) return 'ERROR';
  return data.estado ?? data.estado_dian ?? data.status ?? 'ERROR';
};
