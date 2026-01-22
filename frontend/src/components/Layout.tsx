import {
  Outlet,
  Navigate,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { useEffect, useMemo, useState, useRef, type ReactNode } from "react";
import { useAuth } from "../contexts/AuthContext";
import { configuracionAPI } from "../api/configuracion";
import {
  createFullModuleAccess,
  isModuleEnabled,
  isSectionEnabled,
  normalizeModuleAccess,
} from "../store/moduleAccess";

import {
  ClipboardList,
  Boxes,
  FileText,
  LogOut,
  Menu,
  Settings,
  Wrench,
  X,
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
  const location = useLocation();
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState<Record<string, boolean>>(
    {}
  );

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

  useEffect(() => {
    const storedLogo = localStorage.getItem("empresa_logo");
    if (storedLogo) {
      setLogoUrl(storedLogo);
    }
    const cargarLogo = async () => {
      try {
        const data = await configuracionAPI.obtenerEmpresa();
        if (data?.logo) {
          setLogoUrl(data.logo);
          localStorage.setItem("empresa_logo", data.logo);
        } else {
          setLogoUrl(null);
          localStorage.removeItem("empresa_logo");
        }
      } catch (error) {
        console.error("Error cargando logo:", error);
      }
    };
    cargarLogo();
  }, []);

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const isAdmin = user?.role?.toUpperCase() === "ADMIN";
  const moduleAccess = useMemo(
    () =>
      isAdmin
        ? createFullModuleAccess()
        : normalizeModuleAccess(user?.modulos_permitidos ?? null),
    [isAdmin, user?.modulos_permitidos]
  );
  const moduleEnabled = (key: string) => isModuleEnabled(moduleAccess, key);
  const sectionEnabled = (moduleKey: string, sectionKey: string) =>
    isSectionEnabled(moduleAccess, moduleKey, sectionKey);

  const configuracionItems = useMemo(() => {
    const sections = [
      { label: "Facturación", path: "/configuracion?tab=facturacion", key: "facturacion" },
      { label: "Empresa", path: "/configuracion?tab=empresa", key: "empresa" },
      { label: isAdmin ? "Usuarios" : "Cambiar clave", path: "/configuracion?tab=usuarios", key: "usuarios" },
      { label: "Impuestos", path: "/configuracion?tab=impuestos", key: "impuestos" },
      { label: "Auditoría", path: "/configuracion?tab=auditoria", key: "auditoria" },
    ];

    const filtered = isAdmin
      ? sections
      : sections.filter((section) => sectionEnabled("configuracion", section.key));

    return filtered.map(({ label, path }) => ({ label, path }));
  }, [isAdmin, moduleAccess]);

  useEffect(() => {
    if (isAdmin) {
      return;
    }

    const resolveRouteAccess = (
      pathname: string,
      search: string
    ): { moduleKey: string; sectionKey?: string } | null => {
      if (pathname === "/" || pathname === "") {
        return null;
      }

      if (pathname.startsWith("/configuracion")) {
        const params = new URLSearchParams(search);
        const tab = params.get("tab");
        const resolvedTab = tab === "clave" ? "usuarios" : tab ?? undefined;
        return { moduleKey: "configuracion", sectionKey: resolvedTab };
      }

      if (pathname.startsWith("/listados")) {
        const params = new URLSearchParams(search);
        const tab = params.get("tab") ?? undefined;
        return { moduleKey: "listados", sectionKey: tab };
      }

      if (pathname.startsWith("/articulos")) {
        const params = new URLSearchParams(search);
        const tab = params.get("tab");
        const mappedTab =
          tab === "stock-bajo"
            ? "stock_bajo"
            : tab === "dar-de-baja"
            ? "dar_de_baja"
            : tab ?? undefined;
        return { moduleKey: "articulos", sectionKey: mappedTab };
      }

      if (pathname.startsWith("/taller")) {
        const params = new URLSearchParams(search);
        const tab = params.get("tab") ?? undefined;
        return { moduleKey: "taller", sectionKey: tab };
      }

      if (pathname.startsWith("/ventas/detalles-cuentas")) {
        return { moduleKey: "facturacion", sectionKey: "cuentas" };
      }

      if (pathname.startsWith("/ventas/cuentas-dia")) {
        return { moduleKey: "facturacion", sectionKey: "cuentas" };
      }

      if (pathname.startsWith("/ventas")) {
        return { moduleKey: "facturacion", sectionKey: "venta_rapida" };
      }

      if (pathname.startsWith("/facturacion/facturas")) {
        return { moduleKey: "facturacion", sectionKey: "listados" };
      }

      if (pathname.startsWith("/facturacion/remisiones")) {
        return { moduleKey: "facturacion", sectionKey: "listados" };
      }

      return null;
    };

    const requirement = resolveRouteAccess(
      location.pathname,
      location.search
    );
    if (!requirement) {
      return;
    }

    const allowed = requirement.sectionKey
      ? sectionEnabled(requirement.moduleKey, requirement.sectionKey)
      : moduleEnabled(requirement.moduleKey);

    if (!allowed) {
      navigate("/");
    }
  }, [
    isAdmin,
    location.pathname,
    location.search,
    moduleAccess,
    navigate,
  ]);

  const menuItems = useMemo<MenuItem[]>(
    () => {
      const items: MenuItem[] = [];

      if (configuracionItems.length > 0) {
        items.push({
          label: "Configuración",
          icon: <Settings size={18} />,
          items: configuracionItems,
        });
      }

      {
        const listadosItems = [
          { label: "Clientes", path: "/listados?tab=clientes", key: "clientes" },
          {
            label: "Proveedores",
            path: "/listados?tab=proveedores",
            key: "proveedores",
          },
          {
            label: "Empleados",
            path: "/listados?tab=empleados",
            key: "empleados",
          },
          {
            label: "Categorias",
            path: "/listados?tab=categorias",
            key: "categorias",
          },
          { label: "Mecánicos", path: "/listados?tab=mecanicos", key: "mecanicos" },
        ];
        const filtered = isAdmin
          ? listadosItems
          : listadosItems.filter((item) =>
              sectionEnabled("listados", item.key)
            );
        if (filtered.length > 0) {
          items.push({
            label: "Listados",
            icon: <ClipboardList size={18} />,
            items: filtered.map(({ label, path }) => ({ label, path })),
          });
        }
      }
      {
        const articulosItems = [
          { label: "Mercancia", path: "/articulos?tab=mercancia", key: "mercancia" },
          {
            label: "Stock Bajo",
            path: "/articulos?tab=stock-bajo",
            key: "stock_bajo",
          },
          {
            label: "Dar de Baja",
            path: "/articulos?tab=dar-de-baja",
            key: "dar_de_baja",
          },
        ];
        const filtered = isAdmin
          ? articulosItems
          : articulosItems.filter((item) =>
              sectionEnabled("articulos", item.key)
            );
        if (filtered.length > 0) {
          items.push({
            label: "Artículos",
            icon: <Boxes size={18} />,
            items: filtered.map(({ label, path }) => ({ label, path })),
          });
        }
      }
      {
        const tallerItems = [
          { label: "Operaciones", path: "/taller?tab=ordenes", key: "ordenes" },
          { label: "Registro de Motos", path: "/taller?tab=motos", key: "motos" },
        ];
        const filtered = isAdmin
          ? tallerItems
          : tallerItems.filter((item) => sectionEnabled("taller", item.key));
        if (filtered.length > 0) {
          items.push({
            label: "Taller",
            icon: <Wrench size={18} />,
            items: filtered.map(({ label, path }) => ({ label, path })),
          });
        }
      }
      {
        const facturacionItems: MenuItem[] = [];
        if (isAdmin || sectionEnabled("facturacion", "venta_rapida")) {
          facturacionItems.push({ label: "Venta rápida", path: "/ventas" });
        }
        if (isAdmin || sectionEnabled("facturacion", "cuentas")) {
          facturacionItems.push({
            label: "Cuentas",
            items: [
              { label: "Cuentas del día", path: "/ventas/cuentas-dia" },
              {
                label: "Detalles cuentas",
                path: "/ventas/detalles-cuentas",
              },
            ],
          });
        }
        if (isAdmin || sectionEnabled("facturacion", "listados")) {
          facturacionItems.push({
            label: "Listados",
            items: [
              { label: "Facturas", path: "/facturacion/facturas" },
              { label: "Remisiones", path: "/facturacion/remisiones" },
            ],
          });
        }
        if (facturacionItems.length > 0) {
          items.push({
            label: "Facturación",
            icon: <FileText size={18} />,
            items: facturacionItems,
          });
        }
      }
      // if (moduleEnabled("reportes")) {
      //   items.push({
      //     label: "Reportes",
      //     icon: <Share2 size={18} />,
      //     items: [{ label: "Resumen diario" }, { label: "Resumen mensual" }],
      //   });
      // }

      return items;
    },
    [configuracionItems]
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
    setMobileMenuOpen(false);

    if (item.action) {
      item.action();
      return;
    }
    if (item.path) {
      navigate(item.path);
    }
  };

  const toggleMobileSection = (label: string) => {
    setMobileExpanded((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const renderMobileItems = (items: MenuItem[], level = 0) => (
    <div
      className={
        level === 0
          ? "space-y-2"
          : "mt-2 space-y-1 border-l border-white/20 pl-4"
      }
    >
      {items.map((item) => {
        const hasChildren = Boolean(item.items && item.items.length > 0);
        const isExpanded = Boolean(mobileExpanded[item.label]);

        return (
          <div key={item.label}>
            <button
              type="button"
              onClick={() => {
                if (hasChildren) {
                  toggleMobileSection(item.label);
                } else {
                  onSelectLeaf(item);
                }
              }}
              className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm font-medium text-white/90 hover:bg-white/15"
            >
              <span>{item.label}</span>
              {hasChildren && (
                <span className="text-xs text-white/70">
                  {isExpanded ? "−" : "+"}
                </span>
              )}
            </button>
            {hasChildren && isExpanded && renderMobileItems(item.items!, level + 1)}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="sticky top-0 z-50 bg-blue-600 text-white shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={() => navigate("/")}
            className="flex items-center gap-3 text-left"
            aria-label="Ir al dashboard"
          >
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Logo de la empresa"
                className="h-10 w-10 rounded-lg bg-white/15 object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 text-lg font-bold">
                LA
              </div>
            )}
            <div>
              <h1 className="text-lg font-semibold leading-tight">
                Las Africanas
              </h1>
              <p className="text-xs text-blue-100">Sistema Integrado</p>
            </div>
          </button>

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
            <button
              type="button"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              className="rounded-md border border-white/30 p-2 text-white lg:hidden"
              aria-label="Abrir menú"
            >
              {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        <nav className="hidden flex-wrap items-center justify-center gap-2 border-t border-white/10 px-6 py-2 lg:flex">
          {menuItems.map((item) => (
            <div
              key={item.label}
              className="relative"
              onMouseEnter={() => openMenu(item.label)}
              onMouseLeave={closeMenuWithDelay}
            >
              <button
                type="button"
                onClick={() => {
                  if (!item.items || item.items.length === 0) {
                    onSelectLeaf(item);
                  }
                }}
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

        {mobileMenuOpen && (
          <div className="border-t border-white/10 bg-blue-700 px-4 py-4 lg:hidden">
            {renderMobileItems(menuItems)}
          </div>
        )}
      </header>

      <main className="flex-1 overflow-auto">
        <div className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
