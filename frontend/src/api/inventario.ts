const API_URL = '/api';

export interface Producto {
  id: number;
  codigo: string;
  nombre: string;
  descripcion?: string;
  categoria: number;
  categoria_nombre: string;
  proveedor: number;
  proveedor_nombre: string;
  precio_costo: string;
  precio_venta: string;
  precio_venta_minimo: string;
  stock: number;
  stock_minimo: number;
  stock_bajo: boolean;
  unidad_medida: string;
  iva_porcentaje: string;
  aplica_descuento: boolean;
  es_servicio: boolean;
  margen_utilidad?: number;
  valor_inventario?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductoList {
  id: number;
  codigo: string;
  nombre: string;
  categoria_nombre: string;
  proveedor_nombre: string;
  precio_venta: string;
  stock: number;
  stock_estado: 'AGOTADO' | 'BAJO' | 'OK';
  is_active: boolean;
}

export interface Categoria {
  id: number;
  nombre: string;
  descripcion?: string;
  orden: number;
  is_active: boolean;
  total_productos: number;
}

export interface Proveedor {
  id: number;
  nombre: string;
  nit?: string;
  telefono?: string;
  email?: string;
  direccion?: string;
  ciudad?: string;
  contacto?: string;
  is_active: boolean;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Funciones API
export const inventarioApi = {
  // Productos
  async getProductos(params?: {
    page?: number;
    search?: string;
    categoria?: number;
    proveedor?: number;
  }): Promise<PaginatedResponse<ProductoList>> {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.categoria) queryParams.append('categoria', params.categoria.toString());
    if (params?.proveedor) queryParams.append('proveedor', params.proveedor.toString());

    const response = await fetch(`${API_URL}/productos/?${queryParams}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener productos');
    return response.json();
  },

  async getProducto(id: number): Promise<Producto> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/productos/${id}/`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener producto');
    return response.json();
  },

  async buscarPorCodigo(codigo: string): Promise<Producto> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/productos/buscar_por_codigo/?codigo=${codigo}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Producto no encontrado');
    return response.json();
  },

  async createProducto(data: Partial<Producto>): Promise<Producto> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/productos/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
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

  async updateProducto(id: number, data: Partial<Producto>): Promise<Producto> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/productos/${id}/`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
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

  async deleteProducto(id: number): Promise<void> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/productos/${id}/`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) throw new Error('Error al eliminar producto');
  },

  async getStockBajo(): Promise<ProductoList[]> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/productos/stock_bajo/`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener productos con stock bajo');
    return response.json();
  },

  // Categorías
  async getCategorias(): Promise<Categoria[]> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/categorias/`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener categorías');
    const data = await response.json();
    return data.results || data;
  },

  // Proveedores
  async getProveedores(): Promise<Proveedor[]> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/proveedores/`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Error al obtener proveedores');
    const data = await response.json();
    return data.results || data;
  },
};