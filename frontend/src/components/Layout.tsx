import { Outlet, Navigate, useNavigate } from 'react-router-dom';
import { useMemo, type ReactNode } from 'react';
import { useAuth } from '../contexts/AuthContext';
import {
  Boxes,
  ClipboardList,
  FileText,
  LogOut,
  PackageOpen,
  ReceiptText,
  Settings,
  Share2,
} from 'lucide-react';

export default function Layout() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  type MenuItem = {
    label: string;
    icon?: ReactNode;
    items?: MenuItem[];
    path?: string;
    action?: () => void;
  };

  const menuItems = useMemo<MenuItem[]>(
    () => [
      {
        label: 'Configuración',
        icon: <Settings size={18} />,
        items: [
          { label: 'Facturación', path: '/ventas' },
          { label: 'Empresa' },
          { label: 'Usuarios' },
          { label: 'Impuestos' },
          { label: 'Auditoria' },
          { label: 'Iniciar Sesión', action: () => navigate('/login') },
          { label: 'Cerrar Sesión', action: handleLogout },
          { label: 'Cambiar Clave' },
        ],
      },
      {
        label: 'Registrar',
        icon: <ReceiptText size={18} />,
        items: [
          { label: 'Registro general', path: '/' },
          { label: 'Servicios de taller', path: '/taller' },
        ],
      },
      {
        label: 'Listados',
        icon: <ClipboardList size={18} />,
        items: [
          { label: 'Clientes / Proveedores' },
          { label: 'Empleados' },
          { label: 'Categorias' },
          { label: 'Mecánicos' },
          { label: 'Descuentos Clientes' },
          { label: 'Notas' },
        ],
      },
      {
        label: 'Artículos',
        icon: <Boxes size={18} />,
        items: [
          { label: 'Nuevo', path: '/inventario' },
          { label: 'Mercancia' },
          { label: 'Stock Bajo' },
          { label: 'Nueva Compra' },
          { label: 'Compras' },
          { label: 'Dar de Baja' },
          { label: 'Descargados' },
        ],
      },
      {
        label: 'Entrega M/CIA',
        icon: <Share2 size={18} />,
        items: [
          { label: 'Entrega interna' },
          { label: 'Entrega externa' },
        ],
      },
      {
        label: 'Facturación',
        icon: <FileText size={18} />,
        items: [
          { label: 'Generar Factura', path: '/ventas' },
          {
            label: 'Cuentas',
            items: [
              { label: 'Cuentas del día' },
              { label: 'Detalles Cuentas del día' },
            ],
          },
          {
            label: 'Listados',
            items: [
              { label: 'Facturas' },
              { label: 'Remisiones' },
            ],
          },
        ],
      },
      {
        label: 'Reportes',
        icon: <PackageOpen size={18} />,
        items: [
          { label: 'Resumen diario' },
          { label: 'Resumen mensual' },
        ],
      },
    ],
    [handleLogout, navigate],
  );

  const renderMenuButton = (label: string, icon?: ReactNode) => (
    <>
      {icon}
      <span className="font-medium">{label}</span>
    </>
  );

  const renderDropdownItems = (items: MenuItem[]) => (
    <div className="py-2">
      {items.map((item) => {
        if ('items' in item && item.items) {
          return (
            <div key={item.label} className="relative group/submenu">
              <button
                type="button"
                className="w-full flex items-center justify-between gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-blue-50"
              >
                <span>{item.label}</span>
                <span className="text-slate-400">›</span>
              </button>
              <div className="absolute left-full top-0 ml-1 hidden min-w-[220px] rounded-md border border-slate-200 bg-white shadow-xl group-hover/submenu:block">
                {renderDropdownItems(item.items)}
              </div>
            </div>
          );
        }

        return (
          <button
            key={item.label}
            type="button"
            onClick={() => {
              if (item.action) {
                item.action();
                return;
              }
              if (item.path) {
                navigate(item.path);
              }
            }}
            className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-blue-50"
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="sticky top-0 z-50 bg-blue-600 text-white shadow-lg">
        <div className="flex items-center justify-between gap-6 px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 text-lg font-bold">
              LA
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-tight">Las Africanas</h1>
              <p className="text-xs text-blue-100">Sistema Integrado</p>
            </div>
          </div>

          <nav className="flex flex-1 items-center justify-center gap-2">
            {menuItems.map((item) => (
              <div key={item.label} className="relative group">
                <button
                  type="button"
                  className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-white/90 transition hover:bg-white/15 hover:text-white"
                >
                  {renderMenuButton(item.label, item.icon)}
                </button>
                <div className="absolute left-0 mt-2 hidden min-w-[220px] rounded-md border border-slate-200 bg-white shadow-xl group-hover:block">
                  {renderDropdownItems(item.items)}
                </div>
              </div>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <div className="hidden text-right text-xs text-blue-100 sm:block">
              <p className="font-semibold text-white">{user?.username}</p>
              <p>{user?.role}</p>
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20 text-sm font-semibold">
              {user?.username.charAt(0).toUpperCase()}
            </div>
            <button
              onClick={handleLogout}
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
