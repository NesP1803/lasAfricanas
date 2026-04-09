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
  es_cajero?: boolean;
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
  proveedor: number | null;
  proveedor_nombre: string;
  precio_costo: string;
  precio_venta: string;
  precio_venta_minimo: string;
  stock: string;
  stock_minimo: string;
  stock_bajo: boolean;
  unidad_medida: string;
  iva_porcentaje: string;
  iva_exento?: boolean;
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
  unidad_medida?: string;
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
  numero_comprobante: string | null;
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
  estado: 'BORRADOR' | 'ENVIADA_A_CAJA' | 'FACTURADA' | 'ANULADA';
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
  prefijo_cotizacion?: string;
  numero_cotizacion?: number;
  resolucion: string;
  ambiente_factus?: 'SANDBOX' | 'PRODUCTION';
  factus_numbering_range_id_factura_venta?: number | null;
  factus_numbering_range_id_nota_credito?: number | null;
  factus_numbering_range_id_nota_debito?: number | null;
  factus_numbering_range_id_documento_soporte?: number | null;
  factus_numbering_range_id_nota_ajuste_documento_soporte?: number | null;
  prefijo_factura_electronica?: string;
  factus_factura_venta_document_code?: string;
  factus_factura_venta_range_name?: string;
  factus_factura_venta_range_prefix?: string;
  factus_factura_venta_resolution_number?: string;
  factus_factura_venta_range_from?: number | null;
  factus_factura_venta_range_to?: number | null;
  factus_factura_venta_valid_from?: string | null;
  factus_factura_venta_valid_to?: string | null;
  factus_factura_venta_environment?: 'SANDBOX' | 'PRODUCTION' | string;
  factus_factura_venta_current?: number | null;
  factus_factura_venta_is_valid?: boolean;
  factus_factura_venta_last_sync_at?: string | null;
  factus_nota_credito_document_code?: string;
  factus_nota_credito_range_name?: string;
  factus_nota_credito_range_prefix?: string;
  factus_nota_credito_resolution_number?: string;
  factus_nota_credito_range_from?: number | null;
  factus_nota_credito_range_to?: number | null;
  factus_nota_credito_valid_from?: string | null;
  factus_nota_credito_valid_to?: string | null;
  factus_nota_credito_environment?: string;
  factus_nota_credito_current?: number | null;
  factus_nota_credito_is_valid?: boolean;
  factus_nota_credito_last_sync_at?: string | null;
  factus_nota_debito_document_code?: string;
  factus_nota_debito_range_name?: string;
  factus_nota_debito_range_prefix?: string;
  factus_nota_debito_resolution_number?: string;
  factus_nota_debito_range_from?: number | null;
  factus_nota_debito_range_to?: number | null;
  factus_nota_debito_valid_from?: string | null;
  factus_nota_debito_valid_to?: string | null;
  factus_nota_debito_environment?: string;
  factus_nota_debito_current?: number | null;
  factus_nota_debito_is_valid?: boolean;
  factus_nota_debito_last_sync_at?: string | null;
  factus_documento_soporte_document_code?: string;
  factus_documento_soporte_range_name?: string;
  factus_documento_soporte_range_prefix?: string;
  factus_documento_soporte_resolution_number?: string;
  factus_documento_soporte_range_from?: number | null;
  factus_documento_soporte_range_to?: number | null;
  factus_documento_soporte_valid_from?: string | null;
  factus_documento_soporte_valid_to?: string | null;
  factus_documento_soporte_environment?: string;
  factus_documento_soporte_current?: number | null;
  factus_documento_soporte_is_valid?: boolean;
  factus_documento_soporte_last_sync_at?: string | null;
  factus_nota_ajuste_documento_soporte_document_code?: string;
  factus_nota_ajuste_documento_soporte_range_name?: string;
  factus_nota_ajuste_documento_soporte_range_prefix?: string;
  factus_nota_ajuste_documento_soporte_resolution_number?: string;
  factus_nota_ajuste_documento_soporte_range_from?: number | null;
  factus_nota_ajuste_documento_soporte_range_to?: number | null;
  factus_nota_ajuste_documento_soporte_valid_from?: string | null;
  factus_nota_ajuste_documento_soporte_valid_to?: string | null;
  factus_nota_ajuste_documento_soporte_environment?: string;
  factus_nota_ajuste_documento_soporte_current?: number | null;
  factus_nota_ajuste_documento_soporte_is_valid?: boolean;
  factus_nota_ajuste_documento_soporte_last_sync_at?: string | null;
  modo_operacion_electronica?: 'FACTUS_MANAGED';
  permitir_cache_metadatos_factus?: boolean;
  notas_factura: string;
  plantilla_factura_carta: string;
  plantilla_factura_tirilla: string;
  plantilla_remision_carta: string;
  plantilla_remision_tirilla: string;
  plantilla_nota_credito_carta: string;
  plantilla_nota_credito_tirilla: string;
  redondeo_caja_efectivo?: boolean;
  redondeo_caja_incremento?: number;
}

export interface Impuesto {
  id: number;
  nombre: string;
  porcentaje?: string | number;
  factus_tribute_id?: number | null;
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

export interface AuditoriaRetention {
  retention_days: number;
  archive_retention_days: number;
}

export interface UsuarioAdmin {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  tipo_usuario: 'ADMIN' | 'VENDEDOR' | 'MECANICO' | 'BODEGUERO';
  es_cajero?: boolean;
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
