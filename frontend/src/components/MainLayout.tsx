import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import {
  Home,
  Package,
  ShoppingCart,
  Wrench,
  FileText,
  Users,
  LogOut,
  Settings,
} from 'lucide-react';

export default function MainLayout() {
  const { user, clearAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    clearAuth();
    navigate('/login');
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header estilo SIDEFA */}
      <header className="header-sidefa">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold">LAS AFRICANAS</h1>
            <span className="text-sm opacity-90">
              Sistema de Gestión - Taller y Repuestos
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm">
              {user?.first_name || user?.username} ({user?.tipo_usuario})
            </span>
            <span className="text-sm">Sede: {user?.sede}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-1 bg-red-600 rounded hover:bg-red-700"
            >
              <LogOut size={16} />
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* Menú de navegación */}
      <nav className="bg-gray-800 text-white">
        <div className="flex gap-1 px-4">
          <NavLink to="/" icon={<Home size={18} />} label="Inicio" />
          <NavLink
            to="/productos"
            icon={<Package size={18} />}
            label="Inventario"
          />
          <NavLink
            to="/punto-venta"
            icon={<ShoppingCart size={18} />}
            label="Punto de Venta"
          />
          <NavLink
            to="/taller"
            icon={<Wrench size={18} />}
            label="Taller"
          />
          <NavLink
            to="/reportes"
            icon={<FileText size={18} />}
            label="Reportes"
          />
          {user?.tipo_usuario === 'ADMIN' && (
            <NavLink
              to="/configuracion"
              icon={<Settings size={18} />}
              label="Configuración"
            />
          )}
        </div>
      </nav>

      {/* Contenido principal */}
      <main className="flex-1 p-4 bg-gray-100">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 text-white text-center py-2 text-sm">
        <p>
          © 2026 Las Africanas - Sistema de Gestión | Desarrollado para optimizar
          tu negocio
        </p>
      </footer>
    </div>
  );
}

// Componente auxiliar para los links del menú
function NavLink({
  to,
  icon,
  label,
}: {
  to: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 px-4 py-3 hover:bg-gray-700 transition-colors"
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}