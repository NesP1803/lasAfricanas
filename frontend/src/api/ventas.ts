import type { Cliente, PaginatedResponse } from '../types';

export type { Cliente };

const API_URL = '/api';


const extractApiErrorMessage = (error: unknown, fallback: string): string => {
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
  vendedor: number;
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
  nota_credito_emitida?: {
    id: number;
    number: string;
    status: string;
  };
}

export interface FacturaElectronicaResultado {
  id: number;
  cufe: string;
  uuid: string;
  number: string;
  reference_code: string;
  status: string;
  xml_url: string;
  pdf_url: string;
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
    iva_porcentaje: number;
    total: number;
  }>;
  subtotal: number;
  impuestos: number;
  descuento: number;
  total: number;
  cufe?: string;
  uuid?: string;
  qr_url?: string;
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
  // Clientes
  async buscarCliente(documento: string): Promise<Cliente> {
    const token = localStorage.getItem('token');
    const response = await fetch(
      `${API_URL}/clientes/buscar_por_documento/?documento=${documento}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error('Cliente no encontrado');
    }
    return response.json();
  },

  async getClientes(
    params?: { search?: string; page?: number; ordering?: string; is_active?: boolean }
  ): Promise<PaginatedResponse<Cliente> | Cliente[]> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.ordering) queryParams.append('ordering', params.ordering);
    if (params?.is_active !== undefined) queryParams.append('is_active', String(params.is_active));
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/clientes/${query ? `?${query}` : ''}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Error al obtener clientes');
    }
    return response.json();
  },

  async getCliente(id: number): Promise<Cliente> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/clientes/${id}/`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Error al obtener cliente');
    }
    return response.json();
  },

  async crearCliente(data: Partial<Cliente>): Promise<Cliente> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/clientes/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async actualizarCliente(id: number, data: Partial<Cliente>): Promise<Cliente> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/clientes/${id}/`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    return response.json();
  },

  async eliminarCliente(id: number): Promise<void> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/clientes/${id}/`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Error al eliminar cliente');
    }
  },

  // Ventas
  async crearVenta(data: VentaCreate): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw error;
    }
    return response.json();
  },

  async actualizarVenta(id: number, data: Partial<VentaCreate>): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/${id}/`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw error;
    }
    return response.json();
  },

  async getVentas(params?: {
    tipoComprobante?: string;
    estado?: string;
    search?: string;
    ordering?: string;
    fechaInicio?: string;
    fechaFin?: string;
  }, options?: { signal?: AbortSignal }): Promise<VentaListItem[]> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.tipoComprobante) queryParams.append('tipo_comprobante', params.tipoComprobante);
    if (params?.estado) queryParams.append('estado', params.estado);
    if (params?.search) queryParams.append('search', params.search);
    if (params?.ordering) queryParams.append('ordering', params.ordering);
    if (params?.fechaInicio) queryParams.append('fecha_inicio', params.fechaInicio);
    if (params?.fechaFin) queryParams.append('fecha_fin', params.fechaFin);
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/ventas/${query ? `?${query}` : ''}`, {
      signal: options?.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Error al obtener ventas');
    }
    const data = await response.json();
    if (Array.isArray(data)) {
      return data;
    }
    if (Array.isArray(data?.results)) {
      return data.results;
    }
    throw new Error('Respuesta inválida al obtener ventas');
  },

  async getVenta(id: number): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/${id}/`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Error al obtener la venta');
    }
    return response.json();
  },

  async getRemisionesPendientes(): Promise<Venta[]> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/remisiones_pendientes/`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener remisiones');
    return response.json();
  },

  async enviarACaja(ventaId: number): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/${ventaId}/enviar-a-caja/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Error al enviar a caja');
    }
    return response.json();
  },

  async getPendientesCaja(params?: { fecha?: string }, options?: { signal?: AbortSignal }): Promise<VentaListItem[]> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.fecha) queryParams.append('fecha', params.fecha);
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/caja/pendientes/${query ? `?${query}` : ''}`, {
      signal: options?.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Error al obtener ventas pendientes');
    }
    const data = await response.json();
    if (Array.isArray(data)) {
      return data;
    }
    if (Array.isArray(data?.results)) {
      return data.results;
    }
    return [];
  },

  async getDetalleCaja(ventaId: number, options?: { signal?: AbortSignal }): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/caja/${ventaId}/detalle/`, {
      signal: options?.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, 'Error al cargar venta de caja'));
    }
    return data as Venta;
  },

  async facturarEnCaja(ventaId: number): Promise<FacturarCajaResponse> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/caja/${ventaId}/facturar/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(extractApiErrorMessage(error, 'Error al facturar en caja'));
    }
    const data = await response.json();
    if (data?.venta && data?.factura_electronica) {
      return data;
    }
    return {
      ok: true,
      message: 'Venta facturada correctamente.',
      venta_id: data.id,
      venta: data,
      factura_electronica: {} as FacturaElectronicaResultado,
      numero_factura: data.numero_comprobante || `#${data.id}`,
      estado_local: data.estado || 'FACTURADA',
      status: data.estado || 'FACTURADA',
      factus_sent: false,
    };
  },

  async facturarVentaElectronica(ventaId: number): Promise<FacturarCajaResponse> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/${ventaId}/facturar/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(extractApiErrorMessage(data, 'Error al emitir factura electrónica'));
    }
    if (data?.venta && data?.factura_electronica) {
      return data;
    }
    return {
      ok: true,
      message: data?.message || 'Factura electrónica emitida.',
      venta_id: data?.venta_id || ventaId,
      venta: data?.venta ?? ({} as Venta),
      factura_electronica: data?.factura_electronica ?? ({} as FacturaElectronicaResultado),
      factura_lista: data?.factura_lista,
      numero_factura: data?.numero_factura || '',
      estado_local: data?.estado_local,
      estado_electronico: data?.estado_electronico,
      status: data?.status || data?.estado_electronico || 'ERROR',
      cufe: data?.cufe,
      uuid: data?.uuid,
      reference_code: data?.reference_code,
      send_email: data?.send_email,
      pos_ticket: data?.pos_ticket,
      factus_sent: data?.factus_sent,
      errores: data?.errores,
    };
  },

  async convertirAFactura(remisionId: number): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(
      `${API_URL}/ventas/${remisionId}/convertir_a_factura/`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Error al convertir a factura');
    }
    return response.json();
  },

  async anularVenta(
    ventaId: number,
    data: { motivo: string; descripcion: string; devuelve_inventario: boolean }
  ): Promise<Venta> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/${ventaId}/anular/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      if (response.status === 502) {
        const detail = typeof error?.detail === 'string' && error.detail.trim() ? ` Detalle: ${error.detail}` : '';
        throw new Error(`La venta no fue anulada porque falló Factus al emitir la nota crédito.${detail}`);
      }
      throw new Error(error.error || error.detail || 'Error al anular venta');
    }
    return response.json();
  },

  async getEstadisticasHoy(): Promise<EstadisticasVentas> {
    const hoy = new Date().toISOString().split('T')[0];
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams({
      fecha_inicio: hoy,
      fecha_fin: hoy,
    });
    const response = await fetch(
      `${API_URL}/ventas/estadisticas/?${queryParams.toString()}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) throw new Error('Error al obtener estadísticas');
    return response.json();
  },

  async getEstadisticas(params?: {
    fechaInicio?: string;
    fechaFin?: string;
  }): Promise<EstadisticasVentas> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.fechaInicio) queryParams.append('fecha_inicio', params.fechaInicio);
    if (params?.fechaFin) queryParams.append('fecha_fin', params.fechaFin);
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/ventas/estadisticas/${query ? `?${query}` : ''}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener estadísticas');
    return response.json();
  },
};
