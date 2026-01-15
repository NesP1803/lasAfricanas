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

const STORAGE_KEY = "module_access";

export const loadModuleAccess = (): ModuleAccess => {
  if (typeof window === "undefined") {
    return DEFAULT_MODULE_ACCESS;
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_MODULE_ACCESS;
    }
    const parsed = JSON.parse(raw) as Partial<ModuleAccess>;
    return { ...DEFAULT_MODULE_ACCESS, ...parsed };
  } catch (error) {
    console.error("Error leyendo accesos de módulos:", error);
    return DEFAULT_MODULE_ACCESS;
  }
};

export const saveModuleAccess = (data: ModuleAccess) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
};

export const updateModuleAccess = (partial: Partial<ModuleAccess>) => {
  const current = loadModuleAccess();
  const next = { ...current, ...partial };
  saveModuleAccess(next);
  return next;
};
