import type { Cliente, PaginatedResponse } from '../types';

export type { Cliente };

const API_URL = '/api';

export interface DetalleVenta {
  producto: number;
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
}

export interface Venta {
  id: number;
  numero_comprobante: string;
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
  estado: string;
  estado_display: string;
  detalles: any[];
}

export interface VentaListItem {
  id: number;
  numero_comprobante: string;
  tipo_comprobante: string;
  tipo_comprobante_display: string;
  fecha: string;
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

export interface EstadisticasVentas {
  total_ventas: number;
  total_facturado: string | null;
  total_cotizaciones: number;
  total_remisiones: number;
  total_facturas: number;
  total_facturas_valor: string | null;
  total_remisiones_valor: string | null;
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

  async getClientes(params?: { search?: string; page?: number; ordering?: string }): Promise<PaginatedResponse<Cliente> | Cliente[]> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.search) queryParams.append('search', params.search);
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.ordering) queryParams.append('ordering', params.ordering);
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

  async getVentas(params?: {
    tipoComprobante?: string;
    estado?: string;
    search?: string;
    ordering?: string;
  }): Promise<VentaListItem[]> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    if (params?.tipoComprobante) queryParams.append('tipo_comprobante', params.tipoComprobante);
    if (params?.estado) queryParams.append('estado', params.estado);
    if (params?.search) queryParams.append('search', params.search);
    if (params?.ordering) queryParams.append('ordering', params.ordering);
    const query = queryParams.toString();
    const response = await fetch(`${API_URL}/ventas/${query ? `?${query}` : ''}`, {
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
      throw new Error(error.error || 'Error al anular venta');
    }
    return response.json();
  },

  async getEstadisticasHoy(): Promise<any> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/ventas/estadisticas_hoy/`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

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
