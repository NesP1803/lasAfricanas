import apiClient from '../../../api/client';

export type EstadoDian = 'ACEPTADA' | 'RECHAZADA' | 'EN_PROCESO' | 'ERROR' | string;

export interface FacturaElectronica {
  id?: number;
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
  codigo_error?: string;
  observaciones?: string;
  bill_errors?: string[];
  public_url?: string;
  qr_factus?: string;
  qr_image?: string;
  xml_url?: string;
  pdf_url?: string;
}

interface EstadoFacturaResponse {
  estado?: EstadoDian;
  estado_dian?: EstadoDian;
  status?: EstadoDian;
}

interface SincronizarFacturaResponse {
  detail: string;
  result: 'SYNCED' | 'PENDING' | 'CONFLICT' | 'NOT_PENDING' | 'REMOTE_ERROR' | string;
  factura?: {
    number: string;
    reference_code?: string;
    cufe?: string;
    uuid?: string;
    status?: EstadoDian;
    estado?: EstadoDian;
    estado_dian?: EstadoDian;
    codigo_error?: string;
    mensaje_error?: string;
    pdf_url?: string;
    xml_url?: string;
  };
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

  async sincronizarFactura(facturaId: number) {
    const response = await apiClient.post<SincronizarFacturaResponse>(`/facturacion/${facturaId}/sincronizar/`);
    return response.data;
  },
};

export const resolveEstadoFactura = (data?: EstadoFacturaResponse | FacturaElectronica): EstadoDian => {
  if (!data) return 'ERROR';
  if ((data as FacturaElectronica).codigo_error === 'OBSERVACIONES_FACTUS') {
    return 'EMITIDA_CON_OBSERVACIONES';
  }
  return data.estado ?? data.estado_dian ?? data.status ?? 'ERROR';
};
