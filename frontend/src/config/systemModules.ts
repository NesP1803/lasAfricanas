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
    description: "Maestros de clientes, proveedores, empleados y mecánicos.",
    sections: [
      { key: "clientes", label: "Clientes", path: "/listados?tab=clientes" },
      { key: "proveedores", label: "Proveedores", path: "/listados?tab=proveedores" },
      { key: "empleados", label: "Empleados", path: "/listados?tab=empleados" },
      { key: "mecanicos", label: "Mecánicos", path: "/listados?tab=mecanicos" },
    ],
  },
  {
    key: "reportes",
    label: "Reportes",
    description: "Consultas de cuentas, facturas, remisiones y documentos.",
    sections: [
      { key: "cuentas_dia", label: "Cuentas del día" },
      { key: "detalles_cuentas", label: "Detalles cuentas" },
      { key: "facturas", label: "Facturas" },
      { key: "remisiones", label: "Remisiones" },
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
    description: "Venta rápida, caja y diligenciamiento de documentos.",
    sections: [
      { key: "venta_rapida", label: "Venta rápida", path: "/ventas" },
      { key: "caja", label: "Caja", path: "/facturacion/caja" },
      { key: "nota_credito", label: "Nota crédito", path: "/facturacion/nota-credito" },
      {
        key: "documento_soporte",
        label: "Documento soporte",
        path: "/facturacion/documento-soporte",
      },
    ],
  },
];

export const getSystemModuleByKey = (
  moduleKey: string
): SystemModule | undefined =>
  SYSTEM_MODULES.find((moduleDef) => moduleDef.key === moduleKey);
