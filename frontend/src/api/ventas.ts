import axios from 'axios';
import apiClient from './client';
import type { Cliente, PaginatedResponse } from '../types';

export type { Cliente };

const API_URL = '/api';

const toApiPath = (url: string) => (url.startsWith('/api') ? url.replace(/^\/api/, '') : url);

const apiRequest = async <T>(config: { url: string; method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; data?: unknown; signal?: AbortSignal }) => {
  const response = await apiClient.request<T>({
    ...config,
    url: toApiPath(config.url),
  });
  return response.data;
};


const extractApiErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    return extractApiErrorMessage(error.response?.data, fallback);
  }
  if (typeof error === 'string' && error.trim()) return error;
  if (error && typeof error === 'object') {
    const data = error as Record<string, unknown>;
    const candidates = [data.error, data.detail, data.message];
    for (const item of candidates) {
      if (typeof item === 'string' && item.trim()) return item;
      if (Array.isArray(item) && item.length > 0) {
        const first = item[0];
        if (typeof first === 'string' && first.trim()) return first;
      }
    }
  }
  return fallback;
};

const buildFacturacionErrorMessage = (data: Record<string, unknown>, fallback: string): string => {
  const errorCode = typeof data.error_code === 'string' ? data.error_code : '';
  const estadoVenta = typeof data.estado_venta === 'string' ? data.estado_venta : '';
  const estadoElectronico = typeof data.estado_electronico === 'string' ? data.estado_electronico : '';
  const base = extractApiErrorMessage(data, fallback);
  if (errorCode === 'ERROR_PERSISTENCIA') {
    return `${base} (venta=${estadoVenta || 'N/D'}, electrónico=${estadoElectronico || 'ERROR_PERSISTENCIA'})`;
  }
  return base;
};


export interface DetalleVenta {
  producto: number;
  producto_codigo?: string;
  producto_nombre?: string;
  producto_stock?: string;
  cantidad: number;
  precio_unitario: string;
  descuento_unitario: string;
  iva_porcentaje: string;
  subtotal: string;
  total: string;
}

export interface VentaCreate {
  tipo_comprobante: 'COTIZACION' | 'REMISION' | 'FACTURA';
  cliente: number;
  vendedor?: number;
  subtotal: string;
  descuento_porcentaje: string;
  descuento_valor: string;
  iva: string;
  total: string;
  medio_pago: 'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO';
  efectivo_recibido: string;
  cambio: string;
  observaciones?: string;
  detalles: DetalleVenta[];
  descuento_aprobado_por?: number;
  facturar_directo?: boolean;
}

export interface Venta {
  id: number;
  numero_comprobante: string | null;
  tipo_comprobante: string;
  tipo_comprobante_display: string;
  fecha: string;
  cliente: number;
  cliente_info: Cliente;
  vendedor: number;
  vendedor_nombre: string;
  subtotal: string;
  descuento_porcentaje: string;
  descuento_valor: string;
  iva: string;
  total: string;
  medio_pago: string;
  medio_pago_display: string;
  efectivo_recibido: string;
  cambio: string;
  estado: string;
  estado_display: string;
  creada_por?: number;
  enviada_a_caja_por?: number | null;
  enviada_a_caja_at?: string | null;
  facturada_por?: number | null;
  facturada_at?: string | null;
  detalles: DetalleVenta[];
  factura_electronica?: {
    id: number;
    venta_id: number;
    numero: string;
    number?: string;
    reference_code?: string;
    cufe?: string;
    uuid?: string;
    status?: string;
    estado?: string;
    estado_dian?: string;
    codigo_error?: string;
    observaciones?: string;
    bill_errors?: string[];
    public_url?: string;
    factus_public_url?: string;
    qr_factus?: string;
    qr_image?: string;
    xml_url?: string;
    pdf_url?: string;
    resolucion_numeracion?: string;
    numbering_resolution_info?: Record<string, unknown>;
    print_context?: Record<string, unknown>;
    response_json?: Record<string, unknown>;
  } | null;
  nota_credito_emitida?: {
    id: number;
    number: string;
    status: string;
  };
  result?: 'accepted' | 'pending_dian' | 'rejected' | 'conflict' | 'error' | string;
  finalized?: boolean;
  business_effects_applied?: boolean;
}

export interface FacturaElectronicaResultado {
  id: number;
  cufe: string;
  uuid: string;
  number: string;
  reference_code: string;
  status: string;
  estado_electronico?: string;
  estado_local?: string;
  acciones_sugeridas?: string[];
  observaciones_json?: unknown[];
  xml_url: string;
  pdf_url: string;
  public_url?: string;
  factus_public_url?: string;
  response_json: Record<string, unknown>;
}

export interface FacturaLista {
  id: number;
  number: string;
  numero_visible: string;
  prefix: string;
  status: string;
  estado: string;
  cufe: string;
  uuid: string;
  qr_url?: string;
  qr_image?: string;
  factus_qr?: string;
  public_url?: string;
  bill_errors?: string[];
  observaciones?: string;
  reference_code: string;
  xml_url: string;
  pdf_url: string;
  xml_local_path?: string;
  pdf_local_path?: string;
  cliente: {
    nombre: string;
    documento: string;
    email?: string;
    telefono?: string;
    direccion?: string;
  };
  totales: {
    subtotal: number;
    impuestos: number;
    descuento: number;
    total: number;
    efectivo_recibido: number;
    cambio: number;
  };
}

export interface PosTicketData {
  numero_factura: string;
  fecha_hora: string;
  cliente: {
    nombre: string;
    documento: string;
  };
  vendedor_caja: string;
  items: Array<{
    descripcion: string;
    codigo?: string;
    cantidad: number;
    precio_unitario: number;
    descuento: number;
    subtotal?: number;
    iva_porcentaje: number;
    iva_valor?: number;
    total: number;
  }>;
  discriminacion_iva?: Array<{
    tarifa: number;
    valor_compra: number;
    base_imp: number;
    valor_iva: number;
  }>;
  subtotal: number;
  impuestos: number;
  descuento: number;
  total: number;
  cufe?: string;
  uuid?: string;
  qr_url?: string;
  qr_image?: string;
  factus_qr?: string;
  xml_url?: string;
}

export interface FacturarCajaResponse {
  ok: boolean;
  message: string;
  venta_id?: number;
  venta: Venta;
  factura_electronica: FacturaElectronicaResultado;
  factura_lista?: FacturaLista;
  numero_factura: string;
  number?: string;
  estado_local?: string;
  estado_electronico?: string;
  status: string;
  cufe?: string;
  uuid?: string;
  reference_code?: string;
  send_email?: boolean;
  pos_ticket?: PosTicketData;
  factus_sent?: boolean;
  errores?: string[];
  warnings?: Array<{ component: string; message: string }>;
  xml_disponible?: boolean;
  pdf_disponible?: boolean;
  pdf_subido_factus?: boolean;
  correo_enviado?: boolean;
  correo_error?: string;
  error_code?: string;
}

export interface VentaListItem {
  id: number;
  numero_comprobante: string | null;
  tipo_comprobante: string;
  tipo_comprobante_display: string;
  fecha: string;
  facturada_at?: string | null;
  enviada_a_caja_at?: string | null;
  cliente: number;
  cliente_nombre: string;
  cliente_numero_documento: string;
  vendedor: number;
  vendedor_nombre: string;
  total: string;
  medio_pago: string;
  medio_pago_display: string;
  estado: string;
  estado_display: string;
  estado_electronico?: string | null;
  factura_electronica?: {
    id: number;
    venta_id: number;
    numero: string;
    number?: string;
    reference_code?: string;
    cufe?: string;
    uuid?: string;
    status?: string;
    estado?: string;
    estado_dian?: string;
    codigo_error?: string;
    observaciones?: string;
    bill_errors?: string[];
    public_url?: string;
    factus_public_url?: string;
    qr_factus?: string;
    qr_image?: string;
    xml_url?: string;
    pdf_url?: string;
    resolucion_numeracion?: string;
    numbering_resolution_info?: Record<string, unknown>;
  } | null;
}

export interface CajaPendiente {
  id: number;
  numero_comprobante: string | null;
  tipo_comprobante: string;
  tipo_comprobante_display: string;
  fecha: string;
  cliente_nombre: string;
  total: string;
  estado: string;
  estado_display: string;
}

export interface EstadisticasVentas {
  total_ventas: number;
  total_facturado: string | null;
  total_cotizaciones: number;
  total_remisiones: number;
  total_facturas: number;
  total_facturas_valor: string | null;
  total_remisiones_valor: string | null;
  facturas_por_usuario?: { usuario: string; cuentas: number }[];
  remisiones_por_usuario?: { usuario: string; cuentas: number }[];
}

export const ventasApi = {
  _estadisticasHoyInFlight: null as Promise<EstadisticasVentas> | null,
  _estadisticasInFlight: new Map<string, Promise<EstadisticasVentas>>(),
  // Clientes
  async buscarCliente(documento: string): Promise<Cliente> {
    try {
      return await apiRequest<Cliente>({
        url: `${API_URL}/clientes/buscar_por_documento/?documento=${documento}`,
      });
    } catch {
      throw new Error('Cliente no encontrado');
    }
  },

  async getClientes(
    params?: { search?: string; page?: number; ordering?: string; is_active?: boolean }
  ): Promise<PaginatedResponse<Cliente> | Cliente[]> {
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.ordering) queryParams.append('ordering', params.ordering);
    if (params?.is_active !== undefined) queryParams.append('is_active', String(params.is_active));
    const query = queryParams.toString();
    try {
      return await apiRequest<PaginatedResponse<Cliente> | Cliente[]>({
        url: `${API_URL}/clientes/${query ? `?${query}` : ''}`,
      });
    } catch {
      throw new Error('Error al obtener clientes');
    }
  },

  async getCliente(id: number): Promise<Cliente> {
    try {
      return await apiRequest<Cliente>({ url: `${API_URL}/clientes/${id}/` });
    } catch {
      throw new Error('Error al obtener cliente');
    }
  },

  async crearCliente(data: Partial<Cliente>): Promise<Cliente> {
    try {
      return await apiRequest<Cliente>({
        url: `${API_URL}/clientes/`,
        method: 'POST',
        data,
      });
    } catch (error) {
      throw new Error(JSON.stringify(error));
    }
  },

  async actualizarCliente(id: number, data: Partial<Cliente>): Promise<Cliente> {
    try {
      return await apiRequest<Cliente>({
        url: `${API_URL}/clientes/${id}/`,
        method: 'PATCH',
        data,
      });
    } catch (error) {
      throw new Error(JSON.stringify(error));
    }
  },

  async eliminarCliente(id: number): Promise<void> {
    try {
      await apiRequest<void>({
        url: `${API_URL}/clientes/${id}/`,
        method: 'DELETE',
      });
    } catch {
      throw new Error('Error al eliminar cliente');
    }
  },

  // Ventas
  async crearVenta(data: VentaCreate): Promise<Venta> {
    try {
      return await apiRequest<Venta>({
        url: `${API_URL}/ventas/`,
        method: 'POST',
        data,
      });
    } catch (error) {
      throw new Error(extractApiErrorMessage(error, 'Error al crear la venta'));
    }
  },

  async actualizarVenta(id: number, data: Partial<VentaCreate>): Promise<Venta> {
    try {
      return await apiRequest<Venta>({
        url: `${API_URL}/ventas/${id}/`,
        method: 'PATCH',
        data,
      });
    } catch (error) {
      throw new Error(extractApiErrorMessage(error, 'Error al actualizar la venta'));
    }
  },

  async getVentas(params?: {
    tipoComprobante?: string;
    estado?: string;
    search?: string;
    ordering?: string;
    fechaInicio?: string;
    fechaFin?: string;
  }, options?: { signal?: AbortSignal }): Promise<VentaListItem[]> {
    const queryParams = new URLSearchParams();
    if (params?.tipoComprobante) queryParams.append('tipo_comprobante', params.tipoComprobante);
    if (params?.estado) queryParams.append('estado', params.estado);
    if (params?.search) queryParams.append('search', params.search);
    if (params?.ordering) queryParams.append('ordering', params.ordering);
    if (params?.fechaInicio) queryParams.append('fecha_inicio', params.fechaInicio);
    if (params?.fechaFin) queryParams.append('fecha_fin', params.fechaFin);
    const query = queryParams.toString();
    let data: unknown;
    try {
      data = await apiRequest<unknown>({
        url: `${API_URL}/ventas/${query ? `?${query}` : ''}`,
        signal: options?.signal,
      });
    } catch (error) {
      if (axios.isAxiosError(error) && error.code === 'ERR_CANCELED') {
        throw new DOMException('Solicitud cancelada', 'AbortError');
      }
      throw new Error(extractApiErrorMessage(error, 'Error al obtener ventas'));
    }

    if (Array.isArray(data)) {
      return data as VentaListItem[];
    }
    if (Array.isArray((data as { results?: unknown[] })?.results)) {
      return (data as { results: VentaListItem[] }).results;
    }
    throw new Error('Respuesta inválida al obtener ventas');
  },

  async getVenta(id: number): Promise<Venta> {
    try {
      return await apiRequest<Venta>({ url: `${API_URL}/ventas/${id}/` });
    } catch {
      throw new Error('Error al obtener la venta');
    }
  },

  async getRemisionesPendientes(): Promise<Venta[]> {
    try {
      return await apiRequest<Venta[]>({ url: `${API_URL}/ventas/remisiones_pendientes/` });
    } catch {
      throw new Error('Error al obtener remisiones');
    }
  },

  async enviarACaja(ventaId: number): Promise<Venta> {
    try {
      return await apiRequest<Venta>({
        url: `${API_URL}/ventas/${ventaId}/enviar-a-caja/`,
        method: 'POST',
      });
    } catch (error) {
      throw new Error(extractApiErrorMessage(error, 'Error al enviar a caja'));
    }
  },

  async getPendientesCaja(params?: { fecha?: string }, options?: { signal?: AbortSignal }): Promise<VentaListItem[]> {
    const queryParams = new URLSearchParams();
    if (params?.fecha) queryParams.append('fecha', params.fecha);
    const query = queryParams.toString();
    try {
      const data = await apiRequest<unknown>({
        url: `${API_URL}/caja/pendientes/${query ? `?${query}` : ''}`,
        signal: options?.signal,
      });
      if (Array.isArray(data)) {
        return data as VentaListItem[];
      }
      if (Array.isArray((data as { results?: unknown[] })?.results)) {
        return (data as { results: VentaListItem[] }).results;
      }
      return [];
    } catch {
      throw new Error('Error al obtener ventas pendientes');
    }
  },

  async getDetalleCaja(ventaId: number, options?: { signal?: AbortSignal }): Promise<Venta> {
    try {
      return await apiRequest<Venta>({
        url: `${API_URL}/caja/${ventaId}/detalle/`,
        signal: options?.signal,
      });
    } catch (error) {
      throw new Error(extractApiErrorMessage(error, 'Error al cargar venta de caja'));
    }
  },

  async facturarEnCaja(ventaId: number): Promise<FacturarCajaResponse> {
    const ventaIdNormalizado = Number(ventaId);
    if (!Number.isInteger(ventaIdNormalizado) || ventaIdNormalizado <= 0) {
      throw new Error('No se puede facturar en caja: identificador de venta inválido.');
    }
    let data: unknown;
    try {
      data = await apiRequest<unknown>({
        url: `${API_URL}/caja/${ventaIdNormalizado}/facturar/`,
        method: 'POST',
      });
    } catch (error) {
      throw new Error(extractApiErrorMessage(error, 'Error al facturar en caja'));
    }
    const payload = data as Partial<FacturarCajaResponse> & Record<string, unknown>;
    if (payload?.venta && payload?.factura_electronica) {
      return payload as FacturarCajaResponse;
    }
    return {
      ok: true,
      message: 'Venta facturada correctamente.',
      venta_id: payload.id as number,
      venta: payload as unknown as Venta,
      factura_electronica: {} as FacturaElectronicaResultado,
      numero_factura: (payload.numero_comprobante as string) || `#${String(payload.id ?? '')}`,
      estado_local: (payload.estado as string) || 'FACTURADA',
      status: (payload.estado as string) || 'FACTURADA',
      factus_sent: false,
    };
  },

  async facturarVentaElectronica(ventaId: number): Promise<FacturarCajaResponse> {
    let data: unknown;
    try {
      data = await apiRequest<unknown>({
        url: `${API_URL}/ventas/${ventaId}/facturar/`,
        method: 'POST',
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const statusCode = error.response?.status;
        const responseData = (error.response?.data ?? {}) as Record<string, unknown>;
        const codigoError = String(responseData.codigo_error ?? '');
        if (
          statusCode === 409 ||
          statusCode === 422 ||
          codigoError === 'MISMATCH_DOCUMENTAL' ||
          codigoError === 'MISMATCH_NUMERACION'
        ) {
          const estadoElectronico = String(responseData.estado_electronico ?? 'ERROR');
          throw new Error(
            `${(responseData.mensaje_error as string) || (responseData.message as string) || 'Error de validación documental en emisión FE.'} Estado electrónico: ${estadoElectronico}.`
          );
        }
        const estadoLocal = responseData.estado_local as string | undefined;
        const ventaIdRespuesta = responseData.venta_id as number | undefined;
        const seProcesoVentaLocal = Boolean(ventaIdRespuesta || (estadoLocal && estadoLocal !== 'BORRADOR'));
        if (seProcesoVentaLocal) {
          const estadoElectronico = (responseData.estado_electronico as string) || (responseData.status as string) || '';
          const persistenceMessage =
            estadoElectronico === 'ERROR_PERSISTENCIA'
              ? 'La venta fue registrada, pero ocurrió un error técnico al guardar la respuesta electrónica. Reintenta o sincroniza la factura.'
              : null;
          return {
            ok: false,
            message:
              persistenceMessage ||
              (responseData.message as string) ||
              (responseData.error as string) ||
              'La venta se procesó localmente, pero falló la emisión electrónica.',
            venta_id: ventaIdRespuesta ?? ventaId,
            venta: (responseData.venta as Venta) ?? ({} as Venta),
            factura_electronica: (responseData.factura_electronica as FacturaElectronicaResultado) ?? ({} as FacturaElectronicaResultado),
            factura_lista: responseData.factura_lista as FacturaLista | undefined,
            numero_factura: (responseData.numero_factura as string) || '',
            estado_local: estadoLocal,
            estado_electronico: responseData.estado_electronico as string | undefined,
            status:
              (responseData.status as string) ||
              (responseData.estado_electronico as string) ||
              'ERROR',
            error_code:
              (responseData.error_code as string) ||
              (responseData.codigo_error as string) ||
              undefined,
            cufe: responseData.cufe as string | undefined,
            uuid: responseData.uuid as string | undefined,
            reference_code: responseData.reference_code as string | undefined,
            send_email: responseData.send_email as boolean | undefined,
            pos_ticket: responseData.pos_ticket as PosTicketData | undefined,
            factus_sent: false,
            errores: responseData.errores as string[] | undefined,
          };
        }
      }
      throw new Error(extractApiErrorMessage(error, 'Error al emitir factura electrónica'));
    }
    const payload = data as Partial<FacturarCajaResponse> & Record<string, unknown>;
    if (payload?.venta && payload?.factura_electronica) {
      return payload as FacturarCajaResponse;
    }
    const factusSent = payload.factus_sent as boolean | undefined;
    const ok = typeof payload.ok === 'boolean' ? (payload.ok as boolean) : factusSent !== false;
    return {
      ok,
      message:
        (payload.message as string) ||
        (factusSent === false
          ? 'La venta se procesó localmente, pero falló la emisión electrónica.'
          : 'Factura electrónica emitida.'),
      venta_id: (payload.venta_id as number) || ventaId,
      venta: (payload.venta as Venta) ?? ({} as Venta),
      factura_electronica: (payload.factura_electronica as FacturaElectronicaResultado) ?? ({} as FacturaElectronicaResultado),
      factura_lista: payload.factura_lista as FacturaLista | undefined,
      numero_factura: (payload.numero_factura as string) || '',
      estado_local: payload.estado_local as string | undefined,
      estado_electronico: payload.estado_electronico as string | undefined,
      status: (payload.status as string) || (payload.estado_electronico as string) || 'ERROR',
      error_code: (payload.error_code as string) || (payload.codigo_error as string) || undefined,
      cufe: payload.cufe as string | undefined,
      uuid: payload.uuid as string | undefined,
      reference_code: payload.reference_code as string | undefined,
      send_email: payload.send_email as boolean | undefined,
      pos_ticket: payload.pos_ticket as PosTicketData | undefined,
      factus_sent: factusSent ?? (ok ? true : false),
      errores: payload.errores as string[] | undefined,
    };
  },

  async convertirAFactura(remisionId: number): Promise<FacturarCajaResponse> {
    try {
      const data = await apiRequest<unknown>({
        url: `${API_URL}/ventas/${remisionId}/convertir_a_factura/`,
        method: 'POST',
      });
      const payload = data as Partial<FacturarCajaResponse> & Record<string, unknown>;
      return {
        ok: typeof payload.ok === 'boolean' ? payload.ok : (payload.factus_sent as boolean | undefined) !== false,
        message: (payload.message as string) || 'Factura electrónica emitida.',
        venta_id: (payload.venta_id as number) || remisionId,
        venta: (payload.venta as Venta) ?? ({} as Venta),
        factura_electronica: (payload.factura_electronica as FacturaElectronicaResultado) ?? ({} as FacturaElectronicaResultado),
        factura_lista: payload.factura_lista as FacturaLista | undefined,
        numero_factura: (payload.numero_factura as string) || '',
        estado_local: payload.estado_local as string | undefined,
        estado_electronico: payload.estado_electronico as string | undefined,
        status: (payload.status as string) || (payload.estado_electronico as string) || 'ERROR',
        cufe: payload.cufe as string | undefined,
        uuid: payload.uuid as string | undefined,
        reference_code: payload.reference_code as string | undefined,
        send_email: payload.send_email as boolean | undefined,
        pos_ticket: payload.pos_ticket as PosTicketData | undefined,
        factus_sent:
          typeof payload.factus_sent === 'boolean'
            ? payload.factus_sent
            : typeof payload.ok === 'boolean'
              ? payload.ok
              : true,
        errores: payload.errores as string[] | undefined,
      };
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data && typeof error.response.data === 'object') {
        const data = error.response.data as Record<string, unknown>;
        throw new Error(buildFacturacionErrorMessage(data, 'Error al convertir a factura'));
      }
      throw new Error(extractApiErrorMessage(error, 'Error al convertir a factura'));
    }
  },

  async anularVenta(
    ventaId: number,
    data: { motivo: string; descripcion: string; devuelve_inventario: boolean }
  ): Promise<Venta> {
    try {
      return await apiRequest<Venta>({
        url: `${API_URL}/ventas/${ventaId}/anular/`,
        method: 'POST',
        data,
      });
    } catch (error) {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined;
      const apiError = axios.isAxiosError(error) ? error.response?.data : error;
      if (status === 502) {
        const detail =
          typeof (apiError as { detail?: unknown })?.detail === 'string' &&
          (apiError as { detail: string }).detail.trim()
            ? ` Detalle: ${(apiError as { detail: string }).detail}`
            : '';
        throw new Error(`La venta no fue anulada porque falló Factus al emitir la nota crédito.${detail}`);
      }
      throw new Error(extractApiErrorMessage(apiError, 'Error al anular venta'));
    }
  },

  async getEstadisticasHoy(): Promise<EstadisticasVentas> {
    const hoy = new Date().toISOString().split('T')[0];
    const queryParams = new URLSearchParams({
      fecha_inicio: hoy,
      fecha_fin: hoy,
    });
    if (this._estadisticasHoyInFlight) {
      return this._estadisticasHoyInFlight;
    }
    try {
      this._estadisticasHoyInFlight = apiRequest<EstadisticasVentas>({
        url: `${API_URL}/ventas/estadisticas/?${queryParams.toString()}`,
      });
      return await this._estadisticasHoyInFlight;
    } catch {
      throw new Error('Error al obtener estadísticas');
    } finally {
      this._estadisticasHoyInFlight = null;
    }
  },

  async getEstadisticas(params?: {
    fechaInicio?: string;
    fechaFin?: string;
  }): Promise<EstadisticasVentas> {
    const queryParams = new URLSearchParams();
    if (params?.fechaInicio) queryParams.append('fecha_inicio', params.fechaInicio);
    if (params?.fechaFin) queryParams.append('fecha_fin', params.fechaFin);
    const query = queryParams.toString();
    if (this._estadisticasInFlight.has(query)) {
      return this._estadisticasInFlight.get(query)!;
    }
    try {
      const request = apiRequest<EstadisticasVentas>({
        url: `${API_URL}/ventas/estadisticas/${query ? `?${query}` : ''}`,
      });
      this._estadisticasInFlight.set(query, request);
      return await request;
    } catch {
      throw new Error('Error al obtener estadísticas');
    } finally {
      this._estadisticasInFlight.delete(query);
    }
  },
};
