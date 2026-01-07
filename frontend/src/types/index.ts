// ============================================
// TIPOS DE USUARIO
// ============================================
export interface Usuario {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  tipo_usuario: 'ADMIN' | 'VENDEDOR' | 'MECANICO' | 'BODEGUERO';
  sede: string;
  is_active: boolean;
}

export interface LoginResponse {
  access: string;
  refresh: string;
}

// ============================================
// TIPOS DE INVENTARIO
// ============================================
export interface Categoria {
  id: number;
  nombre: string;
  descripcion: string;
  orden: number;
  total_productos: number;
  is_active: boolean;
}

export interface Proveedor {
  id: number;
  nombre: string;
  nit: string;
  telefono: string;
  email: string;
  ciudad: string;
  is_active: boolean;
}

export interface Producto {
  id: number;
  codigo: string;
  nombre: string;
  descripcion: string;
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
  margen_utilidad: string;
  valor_inventario: string;
  is_active: boolean;
}

// ============================================
// TIPOS DE VENTAS
// ============================================
export interface Cliente {
  id: number;
  tipo_documento: 'CC' | 'NIT' | 'CE' | 'PASAPORTE';
  numero_documento: string;
  nombre: string;
  telefono: string;
  email: string;
  direccion: string;
  ciudad: string;
  is_active: boolean;
}

export interface DetalleVenta {
  id?: number;
  producto: number;
  producto_codigo?: string;
  producto_nombre?: string;
  cantidad: number;
  precio_unitario: string;
  descuento_unitario: string;
  iva_porcentaje: string;
  subtotal: string;
  total: string;
}

export interface Venta {
  id: number;
  tipo_comprobante: 'COTIZACION' | 'REMISION' | 'FACTURA';
  numero_comprobante: string;
  fecha: string;
  cliente: number;
  cliente_nombre?: string;
  vendedor: number;
  vendedor_nombre?: string;
  subtotal: string;
  descuento_porcentaje: string;
  descuento_valor: string;
  iva: string;
  total: string;
  medio_pago: 'EFECTIVO' | 'TRANSFERENCIA' | 'TARJETA' | 'CREDITO';
  efectivo_recibido: string;
  cambio: string;
  estado: 'BORRADOR' | 'CONFIRMADA' | 'ANULADA';
  observaciones: string;
  detalles?: DetalleVenta[];
}

// ============================================
// TIPOS DE TALLER
// ============================================
export interface Mecanico {
  id: number;
  usuario: number;
  usuario_nombre: string;
  usuario_username: string;
  especialidad: string;
  comision_porcentaje: string;
  total_cuentas: string;
  servicios_activos: number;
  is_active: boolean;
}

export interface ServicioMoto {
  id: number;
  numero_servicio: string;
  placa: string;
  marca: string;
  modelo: string;
  color: string;
  cliente: number;
  cliente_nombre?: string;
  mecanico: number;
  mecanico_nombre?: string;
  fecha_ingreso: string;
  fecha_estimada_entrega: string | null;
  fecha_entrega_real: string | null;
  kilometraje: number | null;
  nivel_gasolina: string;
  observaciones_ingreso: string;
  diagnostico: string;
  trabajo_realizado: string;
  recomendaciones: string;
  estado: 'INGRESADO' | 'EN_DIAGNOSTICO' | 'COTIZADO' | 'APROBADO' | 'EN_REPARACION' | 'TERMINADO' | 'ENTREGADO' | 'CANCELADO';
  costo_mano_obra: string;
  costo_repuestos: string;
  descuento: string;
  total: string;
}

// ============================================
// TIPOS DE RESPUESTA DE API
// ============================================
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  detail?: string;
  error?: string;
  [key: string]: any;
}