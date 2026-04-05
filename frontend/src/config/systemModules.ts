export type SystemModuleSection = {
  key: string;
  label: string;
  path?: string;
};

export type SystemModule = {
  key: string;
  label: string;
  description?: string;
  sections: SystemModuleSection[];
};

export const SYSTEM_MODULES: SystemModule[] = [
  {
    key: "configuracion",
    label: "Configuración",
    description: "Permite acceder a la información y ajustes del sistema.",
    sections: [
      { key: "facturacion", label: "Facturación", path: "/configuracion?tab=facturacion" },
      { key: "empresa", label: "Empresa", path: "/configuracion?tab=empresa" },
      { key: "usuarios", label: "Usuarios", path: "/configuracion?tab=usuarios" },
      { key: "impuestos", label: "Impuestos", path: "/configuracion?tab=impuestos" },
      { key: "auditoria", label: "Auditoría", path: "/configuracion?tab=auditoria" },
    ],
  },
  {
    key: "listados",
    label: "Listados",
    description:
      "Acceso a clientes, proveedores, empleados, categorías y consultas de facturación.",
    sections: [
      { key: "clientes", label: "Clientes" },
      { key: "proveedores", label: "Proveedores" },
      { key: "empleados", label: "Empleados" },
      { key: "categorias", label: "Categorías" },
      { key: "mecanicos", label: "Mecánicos" },
      { key: "cuentas", label: "Cuentas" },
      { key: "listados", label: "Facturas y remisiones" },
      { key: "notas_credito", label: "Notas crédito" },
      { key: "documentos_soporte", label: "Documentos soporte" },
    ],
  },
  {
    key: "articulos",
    label: "Artículos",
    description: "Inventario, stock y bajas de mercancía.",
    sections: [
      { key: "mercancia", label: "Mercancía", path: "/articulos?tab=mercancia" },
      { key: "stock_bajo", label: "Stock Bajo", path: "/articulos?tab=stock_bajo" },
    ],
  },
  {
    key: "taller",
    label: "Taller",
    description: "Operaciones y registro de motos del taller.",
    sections: [
      { key: "ordenes", label: "Operaciones", path: "/taller?tab=ordenes" },
      { key: "motos", label: "Registro de Motos", path: "/taller?tab=motos" },
    ],
  },
  {
    key: "facturacion",
    label: "Facturación",
    description: "Venta rápida, cuentas y listados de facturas.",
    sections: [
      { key: "venta_rapida", label: "Venta rápida", path: "/ventas" },
      { key: "caja", label: "Caja", path: "/facturacion/caja" },
      { key: "cuentas", label: "Cuentas" },
      { key: "listados", label: "Listados" },
    ],
  },
];

export const getSystemModuleByKey = (
  moduleKey: string
): SystemModule | undefined =>
  SYSTEM_MODULES.find((moduleDef) => moduleDef.key === moduleKey);
