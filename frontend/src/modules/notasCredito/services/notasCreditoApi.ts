import apiClient from '../../../api/client';

export type EstadoDian =
  | 'ACEPTADA'
  | 'ACEPTADA_CON_OBSERVACIONES'
  | 'RECHAZADA'
  | 'EN_PROCESO'
  | 'CONFLICTO_FACTUS'
  | 'ERROR_INTEGRACION'
  | 'ERROR_PERSISTENCIA'
  | 'PENDIENTE_REINTENTO'
  | string;

export interface NotaCreditoDetalle {
  id: number;
  detalle_venta_original: number;
  producto: number;
  producto_nombre: string;
  cantidad_original_facturada: string;
  cantidad_ya_acreditada: string;
  cantidad_a_acreditar: string;
  precio_unitario: string;
  descuento: string;
  base_impuesto: string;
  impuesto: string;
  total_linea: string;
  afecta_inventario: boolean;
  motivo_linea?: string;
}

export interface NotaCredito {
  id: number;
  numero: string;
  factura_asociada: string;
  fecha: string;
  motivo: string;
  tipo_nota?: 'PARCIAL' | 'TOTAL' | string;
  estado?: EstadoDian;
  estado_dian: EstadoDian;
  estado_local?: string;
  estado_electronico?: string;
  cufe?: string;
  uuid?: string;
  xml_url?: string;
  pdf_url?: string;
  public_url?: string;
  correo_enviado?: boolean;
  correo_enviado_at?: string;
  email_status?: string;
  codigo_error?: string;
  mensaje_error?: string;
  synchronized_at?: string;
  can_sync?: boolean;
  estado_ui_mensaje?: string;
  detail?: string;
  detalles?: NotaCreditoDetalle[];
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

  async getFacturasElectronicas() {
    const response = await apiClient.get<
      Array<{
        id: number;
        venta_id?: number;
        numero: string;
        cliente: string;
        fecha: string;
        total: number;
        cufe?: string;
        estado?: string;
        estado_electronico?: string;
      }>
    >('/facturas-electronicas/');
    return response.data;
  },

  async getVenta(ventaId: number) {
    const response = await apiClient.get<{
      id: number;
      cliente_info?: { nombre?: string; documento?: string };
      detalles: Array<{
        id: number;
        producto: number;
        producto_codigo?: string;
        producto_nombre?: string;
        cantidad: number;
        precio_unitario: string;
        iva_porcentaje: string;
      }>;
      subtotal: string;
      iva: string;
      total: string;
      fecha: string;
    }>(`/ventas/${ventaId}/`);
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

  async descargarXML(id: number, numero: string) {
    const response = await apiClient.get<Blob>(`/notas-credito/${id}/xml/`, {
      responseType: 'blob',
    });
    crearArchivoDescargable(response.data, `nota-credito-${encodeURIComponent(numero)}.xml`);
  },

  async descargarPDF(id: number, numero: string) {
    const response = await apiClient.get<Blob>(`/notas-credito/${id}/pdf/`, {
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
    const response = await apiClient.delete(`/notas-credito/${id}/`);
    return response.data;
  },
};
