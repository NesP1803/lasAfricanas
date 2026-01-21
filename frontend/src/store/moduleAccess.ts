export type ModuleKey =
  | "configuracion"
  | "registrar"
  | "listados"
  | "articulos"
  | "taller"
  | "taller_operaciones"
  | "taller_registro_motos"
  | "facturacion"
  | "facturacion_venta_rapida"
  | "facturacion_cuentas"
  | "facturacion_listado_facturas"
  | "reportes";

export type ModuleAccess = Record<ModuleKey, boolean>;

export const DEFAULT_MODULE_ACCESS: ModuleAccess = {
  configuracion: true,
  registrar: true,
  listados: true,
  articulos: true,
  taller: true,
  taller_operaciones: true,
  taller_registro_motos: true,
  facturacion: true,
  facturacion_venta_rapida: true,
  facturacion_cuentas: true,
  facturacion_listado_facturas: true,
  reportes: true,
};
