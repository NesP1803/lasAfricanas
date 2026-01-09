const API_URL = '/api';

export interface Cliente {
  id: number;
  tipo_documento: string;
  numero_documento: string;
  nombre: string;
  telefono?: string;
  email?: string;
  direccion?: string;
  ciudad?: string;
}

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
};