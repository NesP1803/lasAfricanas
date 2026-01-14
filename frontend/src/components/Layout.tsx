import { Outlet, Navigate, useNavigate } from "react-router-dom";
import { useMemo, useState, useRef, type ReactNode } from "react";
import { useAuth } from "../contexts/AuthContext";
import {
  ClipboardList,
  Boxes,
  FileText,
  LogOut,
  PackageOpen,
  ReceiptText,
  Settings,
  Share2,
} from "lucide-react";

type MenuItem = {
  label: string;
  icon?: ReactNode;
  items?: MenuItem[];
  path?: string;
  action?: () => void;
};

const CLOSE_DELAY_MS = 450;

// --- Submenú con delay (para items con hijos) ---
function DropdownItem({
  item,
  onSelectLeaf,
}: {
  item: MenuItem;
  onSelectLeaf: (item: MenuItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openNow = () => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    setOpen(true);
  };

  const closeWithDelay = () => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    closeTimeoutRef.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  };

  // Item con sub-items
  if (item.items && item.items.length > 0) {
    return (
      <div
        className="relative"
        onMouseEnter={openNow}
        onMouseLeave={closeWithDelay}
      >
        <button
          type="button"
          className="w-full flex items-center justify-between gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-blue-50"
        >
          <span>{item.label}</span>
          <span className="text-slate-400">›</span>
        </button>

        {open && (
          <div
            className="absolute left-full top-0 ml-1 min-w-[220px] rounded-md border border-slate-200 bg-white shadow-xl"
            onMouseEnter={openNow}
            onMouseLeave={closeWithDelay}
          >
            <DropdownList items={item.items} onSelectLeaf={onSelectLeaf} />
          </div>
        )}
      </div>
    );
  }

  // Item hoja (navega o ejecuta acción)
  return (
    <button
      type="button"
      onClick={() => onSelectLeaf(item)}
      className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-blue-50"
    >
      {item.label}
    </button>
  );
}

function DropdownList({
  items,
  onSelectLeaf,
}: {
  items: MenuItem[];
  onSelectLeaf: (item: MenuItem) => void;
}) {
  return (
    <div className="py-2">
      {items.map((it) => (
        <DropdownItem key={it.label} item={it} onSelectLeaf={onSelectLeaf} />
      ))}
    </div>
  );
}

export default function Layout() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  // --- Menú principal con delay ---
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const openMenu = (label: string) => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    setActiveMenu(label);
  };

  const closeMenuWithDelay = () => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    closeTimeoutRef.current = setTimeout(() => {
      setActiveMenu(null);
    }, CLOSE_DELAY_MS);
  };

  const closeMenuNow = () => {
    if (closeTimeoutRef.current) clearTimeout(closeTimeoutRef.current);
    setActiveMenu(null);
  };

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const menuItems = useMemo<MenuItem[]>(
    () => [
      {
        label: "Configuración",
        icon: <Settings size={18} />,
        items: [
          { label: "Facturación", path: "/configuracion?tab=facturacion" },
          { label: "Empresa", path: "/configuracion?tab=empresa" },
          { label: "Usuarios", path: "/configuracion?tab=usuarios" },
          { label: "Impuestos", path: "/configuracion?tab=impuestos" },
          { label: "Auditoría", path: "/configuracion?tab=auditoria" },
          { label: "Cambiar Clave", path: "/configuracion?tab=clave" },
        ],
      },
      {
        label: "Registrar",
        icon: <ReceiptText size={18} />,
        items: [
          { label: "Registro general", path: "/" },
          { label: "Servicios de taller", path: "/taller" },
        ],
      },
      {
        label: "Listados",
        icon: <ClipboardList size={18} />,
        items: [
          { label: "Clientes", path: "/listados?tab=clientes" },
          { label: "Proveedores", path: "/listados?tab=proveedores" },
          { label: "Empleados", path: "/listados?tab=empleados" },
          { label: "Categorias", path: "/listados?tab=categorias" },
          { label: "Mecánicos", path: "/listados?tab=mecanicos" },
        ],
      },
      {
        label: "Artículos",
        icon: <Boxes size={18} />,
        items: [
          { label: "Mercancia", path: "/articulos?tab=mercancia" },
          { label: "Stock Bajo", path: "/articulos?tab=stock-bajo" },
          { label: "Nueva Compra", path: "/articulos?tab=nueva-compra" },
          { label: "Dar de Baja", path: "/articulos?tab=dar-de-baja" },
        ],
      },
      {
        label: "Entrega M/CIA",
        icon: <PackageOpen size={18} />,
        items: [
          { label: "Registrar Moto a Mecanico" },
          { label: " Listado de Motos" },
        ],
      },
      {
        label: "Facturación",
        icon: <FileText size={18} />,
        items: [
          { label: "Generar Factura", path: "/ventas" },
          {
            label: "Cuentas",
            items: [
              { label: "Cuentas del día" },
              { label: "Detalles Cuentas del día" },
            ],
          },
          {
            label: "Listados",
            items: [{ label: "Facturas" }, { label: "Remisiones" }],
          },
        ],
      },
      {
        label: "Reportes",
        icon: <Share2 size={18} />,
        items: [{ label: "Resumen diario" }, { label: "Resumen mensual" }],
      },
    ],
    [navigate]
  );

  const renderMenuButton = (label: string, icon?: ReactNode) => (
    <>
      {icon}
      <span className="font-medium">{label}</span>
    </>
  );

  const onSelectLeaf = (item: MenuItem) => {
    // Cierra todo el menú al seleccionar
    closeMenuNow();

    if (item.action) {
      item.action();
      return;
    }
    if (item.path) {
      navigate(item.path);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="sticky top-0 z-50 bg-blue-600 text-white shadow-lg">
        <div className="flex items-center justify-between gap-6 px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 text-lg font-bold">
              LA
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                Las Africanas
              </h1>
              <p className="text-xs text-blue-100">Sistema Integrado</p>
            </div>
          </div>

          <nav className="flex flex-1 items-center justify-center gap-2">
            {menuItems.map((item) => (
              <div
                key={item.label}
                className="relative"
                onMouseEnter={() => openMenu(item.label)}
                onMouseLeave={closeMenuWithDelay}
              >
                <button
                  type="button"
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-white/90 transition hover:bg-white/15 hover:text-white"
                >
                  {renderMenuButton(item.label, item.icon)}
                </button>

                {activeMenu === item.label && (
                  <div
                    className="absolute left-0 mt-2 min-w-[220px] rounded-md border border-slate-200 bg-white shadow-xl"
                    onMouseEnter={() => openMenu(item.label)}
                    onMouseLeave={closeMenuWithDelay}
                  >
                    <DropdownList
                      items={item.items ?? []}
                      onSelectLeaf={onSelectLeaf}
                    />
                  </div>
                )}
              </div>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <div className="hidden text-right text-xs text-blue-100 sm:block">
              <p className="font-semibold text-white">{user?.username}</p>
              <p>{user?.role}</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20 text-sm font-semibold">
              {user?.username?.charAt(0)?.toUpperCase()}
            </div>
            <button
              onClick={() => {
                closeMenuNow();
                handleLogout();
              }}
              className="flex items-center gap-2 rounded-md bg-white/10 px-3 py-2 text-sm font-medium text-white transition hover:bg-white/20"
            >
              <LogOut size={16} />
              <span className="hidden sm:inline">Salir</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
