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

export type ModulosPermitidos = Record<
  string,
  | boolean
  | string[]
  | Record<string, boolean>
  | {
      enabled?: boolean;
      sections?: Record<string, boolean> | string[];
    }
>;

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
// TIPOS DE CONFIGURACIÓN
// ============================================
export interface ConfiguracionEmpresa {
  id: number;
  tipo_identificacion: 'NIT' | 'CC' | 'CE';
  identificacion: string;
  dv: string;
  tipo_persona: 'Persona natural' | 'Persona jurídica';
  razon_social: string;
  regimen: 'RÉGIMEN COMÚN' | 'RÉGIMEN SIMPLIFICADO';
  direccion: string;
  ciudad: string;
  municipio: string;
  telefono: string;
  sitio_web: string;
  correo: string;
  logo: string | null;
}

export interface ConfiguracionFacturacion {
  id: number;
  prefijo_factura: string;
  numero_factura: number;
  prefijo_remision: string;
  numero_remision: number;
  resolucion: string;
  notas_factura: string;
  plantilla_factura_carta: string;
  plantilla_factura_tirilla: string;
  plantilla_remision_carta: string;
  plantilla_remision_tirilla: string;
  plantilla_nota_credito_carta: string;
  plantilla_nota_credito_tirilla: string;
}

export interface Impuesto {
  id: number;
  nombre: string;
  is_active?: boolean;
}

export interface AuditoriaRegistro {
  id: number;
  fecha_hora: string;
  usuario_nombre: string;
  accion: string;
  modelo: string;
  objeto_id: string;
  notas: string;
  ip_address: string | null;
}

export interface UsuarioAdmin {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  tipo_usuario: 'ADMIN' | 'VENDEDOR' | 'MECANICO' | 'BODEGUERO';
  telefono?: string;
  sede?: string;
  is_active: boolean;
  last_login: string | null;
  date_joined: string;
  modulos_permitidos?: ModulosPermitidos | null;
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
