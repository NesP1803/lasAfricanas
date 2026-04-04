import apiClient from '../../../api/client';

export type EstadoDian =
  | 'ACEPTADA'
  | 'ACEPTADA_CON_OBSERVACIONES'
  | 'RECHAZADA'
  | 'ERROR_INTEGRACION'
  | 'ERROR_PERSISTENCIA'
  | 'PENDIENTE_REINTENTO'
  | string;

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
  estado_electronico?: EstadoDian;
  estado_local?: string;
  acciones_sugeridas?: string[];
  codigo_error?: string;
  observaciones?: string;
  bill_errors?: string[];
  public_url?: string;
  qr_factus?: string;
  qr_image?: string;
  xml_url?: string;
  pdf_url?: string;
  xml_local_path?: string;
  pdf_local_path?: string;
  pdf_uploaded_to_factus?: boolean;
  correo_enviado?: boolean;
  correo_enviado_at?: string;
  ultimo_error_correo?: string;
  response_json?: Record<string, unknown>;
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
    const response = await apiClient.get<FacturaElectronica[]>('/facturas-electronicas/');
    return response.data;
  },

  async getEstadoFactura(numero: string) {
    const response = await apiClient.get<EstadoFacturaResponse>(`/facturacion/${encodeURIComponent(numero)}/estado/`);
    return response.data;
  },

  async descargarXMLById(id: number, numero: string) {
    const response = await apiClient.get<Blob>(`/facturas-electronicas/${id}/xml/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `factura-${encodeURIComponent(numero)}.xml`);
  },

  async descargarPDFById(id: number, numero: string) {
    const response = await apiClient.get<Blob>(`/facturas-electronicas/${id}/pdf/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `factura-${encodeURIComponent(numero)}.pdf`);
  },

  async enviarFacturaCorreoById(id: number) {
    const response = await apiClient.post(`/facturas-electronicas/${id}/enviar-correo/`);
    return response.data;
  },

  async sincronizarFactura(facturaId: number) {
    const response = await apiClient.post<SincronizarFacturaResponse>(`/facturas-electronicas/${facturaId}/sincronizar/`);
    return response.data;
  },

  async obtenerContenidoCorreo(facturaId: number) {
    const response = await apiClient.get(`/facturas-electronicas/${facturaId}/correo/contenido/`);
    return response.data;
  },

  async consultarEventos(facturaId: number) {
    const response = await apiClient.get(`/facturas-electronicas/${facturaId}/eventos/`);
    return response.data;
  },

  async ejecutarAceptacionTacita(facturaId: number) {
    const response = await apiClient.post(`/facturas-electronicas/${facturaId}/aceptacion-tacita/`);
    return response.data;
  },

  async eliminarFacturaElectronica(facturaId: number) {
    const response = await apiClient.post(`/facturas-electronicas/${facturaId}/eliminar/`);
    return response.data;
  },
};

export const resolveEstadoFactura = (data?: EstadoFacturaResponse | FacturaElectronica): EstadoDian => {
  if (!data) return 'ERROR';
  return (data as FacturaElectronica).estado_electronico ?? data.estado ?? data.estado_dian ?? data.status ?? 'ERROR_INTEGRACION';
};
