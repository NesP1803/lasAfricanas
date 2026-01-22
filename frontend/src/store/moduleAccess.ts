import type { ModulosPermitidos } from "../types";

export type ModuleSection = {
  key: string;
  label: string;
};

export type ModuleDefinition = {
  key: string;
  label: string;
  description?: string;
  sections?: ModuleSection[];
};

export type ModuleAccessEntry = {
  enabled: boolean;
  sections: Record<string, boolean>;
};

export type ModuleAccessState = Record<string, ModuleAccessEntry>;

export const MODULE_DEFINITIONS: ModuleDefinition[] = [
  {
    key: "configuracion",
    label: "Configuración",
    description: "Permite acceder a la información y ajustes del sistema.",
    sections: [
      { key: "facturacion", label: "Facturación" },
      { key: "empresa", label: "Empresa" },
      { key: "usuarios", label: "Usuarios" },
      { key: "impuestos", label: "Impuestos" },
      { key: "auditoria", label: "Auditoría" },
    ],
  },
  {
    key: "listados",
    label: "Listados",
    description: "Acceso a clientes, proveedores, empleados y categorías.",
    sections: [
      { key: "clientes", label: "Clientes" },
      { key: "proveedores", label: "Proveedores" },
      { key: "empleados", label: "Empleados" },
      { key: "categorias", label: "Categorías" },
      { key: "mecanicos", label: "Mecánicos" },
    ],
  },
  {
    key: "articulos",
    label: "Artículos",
    description: "Inventario, stock y bajas de mercancía.",
    sections: [
      { key: "mercancia", label: "Mercancía" },
      { key: "stock_bajo", label: "Stock bajo" },
      { key: "dar_de_baja", label: "Dar de baja" },
    ],
  },
  {
    key: "taller",
    label: "Taller",
    description: "Operaciones y registro de motos del taller.",
    sections: [
      { key: "ordenes", label: "Operaciones" },
      { key: "motos", label: "Registro de motos" },
    ],
  },
  {
    key: "facturacion",
    label: "Facturación",
    description: "Venta rápida, cuentas y listados de facturas.",
    sections: [
      { key: "venta_rapida", label: "Venta rápida" },
      { key: "cuentas", label: "Cuentas" },
      { key: "listados", label: "Listados" },
    ],
  },
];

export const createEmptyModuleAccess = (): ModuleAccessState => {
  return MODULE_DEFINITIONS.reduce<ModuleAccessState>((acc, moduleDef) => {
    const sections = (moduleDef.sections ?? []).reduce<Record<string, boolean>>(
      (sectionAcc, section) => {
        sectionAcc[section.key] = false;
        return sectionAcc;
      },
      {}
    );
    acc[moduleDef.key] = {
      enabled: false,
      sections,
    };
    return acc;
  }, {});
};

export const createFullModuleAccess = (): ModuleAccessState => {
  return MODULE_DEFINITIONS.reduce<ModuleAccessState>((acc, moduleDef) => {
    const sections = (moduleDef.sections ?? []).reduce<Record<string, boolean>>(
      (sectionAcc, section) => {
        sectionAcc[section.key] = true;
        return sectionAcc;
      },
      {}
    );
    acc[moduleDef.key] = {
      enabled: true,
      sections,
    };
    return acc;
  }, {});
};

export const normalizeModuleAccess = (
  access?: ModulosPermitidos | null
): ModuleAccessState => {
  const normalized = createEmptyModuleAccess();
  if (!access) {
    return normalized;
  }

  MODULE_DEFINITIONS.forEach((moduleDef) => {
    const incoming = access[moduleDef.key];
    if (!incoming) {
      return;
    }
    normalized[moduleDef.key].enabled = Boolean(incoming.enabled);
    (moduleDef.sections ?? []).forEach((section) => {
      normalized[moduleDef.key].sections[section.key] = Boolean(
        incoming.sections?.[section.key]
      );
    });
  });

  return normalized;
};

export const isModuleEnabled = (
  access: ModuleAccessState,
  moduleKey: string
): boolean => {
  const moduleEntry = access[moduleKey];
  if (!moduleEntry) {
    return false;
  }
  if (moduleEntry.enabled) {
    return true;
  }
  return Object.values(moduleEntry.sections ?? {}).some(Boolean);
};

export const isSectionEnabled = (
  access: ModuleAccessState,
  moduleKey: string,
  sectionKey: string
): boolean => {
  const moduleEntry = access[moduleKey];
  return Boolean(moduleEntry?.sections?.[sectionKey]);
};
