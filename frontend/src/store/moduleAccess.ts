export type ModuleKey =
  | "configuracion"
  | "registrar"
  | "listados"
  | "articulos"
  | "taller"
  | "facturacion"
  | "reportes";

export type ModuleSection = {
  key: string;
  label: string;
  description?: string;
};

export type ModuleDefinition = {
  key: ModuleKey;
  label: string;
  description: string;
  sections?: ModuleSection[];
};

export type ModuleAccessEntry = {
  enabled: boolean;
  sections: Record<string, boolean>;
};

export type ModuleAccess = Record<ModuleKey, ModuleAccessEntry>;

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
      { key: "accesos", label: "Accesos" },
      { key: "clave", label: "Cambiar clave" },
    ],
  },
  {
    key: "registrar",
    label: "Registrar",
    description: "Habilita el registro general de operaciones.",
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
  {
    key: "reportes",
    label: "Reportes",
    description: "Visualización de reportes diarios y mensuales.",
  },
];

const buildDefaultModuleAccess = (): ModuleAccess =>
  MODULE_DEFINITIONS.reduce((acc, definition) => {
    const sections =
      definition.sections?.reduce<Record<string, boolean>>((sectionAcc, section) => {
        sectionAcc[section.key] = true;
        return sectionAcc;
      }, {}) ?? {};

    acc[definition.key] = {
      enabled: true,
      sections,
    };
    return acc;
  }, {} as ModuleAccess);

const buildEmptyModuleAccess = (): ModuleAccess =>
  MODULE_DEFINITIONS.reduce((acc, definition) => {
    const sections =
      definition.sections?.reduce<Record<string, boolean>>((sectionAcc, section) => {
        sectionAcc[section.key] = false;
        return sectionAcc;
      }, {}) ?? {};

    acc[definition.key] = {
      enabled: false,
      sections,
    };
    return acc;
  }, {} as ModuleAccess);

export const DEFAULT_MODULE_ACCESS: ModuleAccess = buildDefaultModuleAccess();
export const EMPTY_MODULE_ACCESS: ModuleAccess = buildEmptyModuleAccess();

export const normalizeModuleAccess = (
  access?: Partial<ModuleAccess> | null
): ModuleAccess => {
  const base = access ? buildEmptyModuleAccess() : buildDefaultModuleAccess();
  if (!access) {
    return base;
  }

  const normalized = { ...base };

  (Object.keys(base) as ModuleKey[]).forEach((key) => {
    const entry = access[key];
    if (!entry) {
      return;
    }

    const baseEntry = base[key];
    const sections = { ...baseEntry.sections };

    if (entry.sections) {
      Object.entries(entry.sections).forEach(([sectionKey, enabled]) => {
        sections[sectionKey] = enabled;
      });
    }

    const hasSections = Object.keys(sections).length > 0;
    const anySectionEnabled = hasSections
      ? Object.values(sections).some(Boolean)
      : entry.enabled ?? baseEntry.enabled;

    normalized[key] = {
      enabled: hasSections ? anySectionEnabled : entry.enabled ?? baseEntry.enabled,
      sections,
    };
  });

  return normalized;
};

export const isModuleEnabled = (access: ModuleAccess, key: ModuleKey) => {
  const entry = access[key];
  if (!entry) {
    return false;
  }
  const sectionValues = Object.values(entry.sections);
  if (sectionValues.length > 0) {
    return sectionValues.some(Boolean);
  }
  return entry.enabled;
};

export const isSectionEnabled = (
  access: ModuleAccess,
  moduleKey: ModuleKey,
  sectionKey: string
) => {
  const entry = access[moduleKey];
  if (!entry) {
    return false;
  }
  if (entry.sections && sectionKey in entry.sections) {
    return entry.sections[sectionKey];
  }
  return entry.enabled;
};
