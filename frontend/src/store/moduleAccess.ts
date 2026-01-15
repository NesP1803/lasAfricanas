export type ModuleKey =
  | "configuracion"
  | "registrar"
  | "listados"
  | "articulos"
  | "taller"
  | "facturacion"
  | "reportes";

export type ModuleAccess = Record<ModuleKey, boolean>;

export const DEFAULT_MODULE_ACCESS: ModuleAccess = {
  configuracion: true,
  registrar: true,
  listados: true,
  articulos: true,
  taller: true,
  facturacion: true,
  reportes: true,
};
