import { Outlet, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard,
  Package,
  Wrench,
  ShoppingCart,
  Users,
  Settings,
  LogOut,
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

  const menuItems = [
    { icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/' },
    { icon: <Package size={20} />, label: 'Inventario', path: '/inventario' },
    { icon: <Wrench size={20} />, label: 'Taller', path: '/taller' },
    { icon: <ShoppingCart size={20} />, label: 'Ventas', path: '/ventas' },
    { icon: <Users size={20} />, label: 'Clientes', path: '/clientes' },
    { icon: <Settings size={20} />, label: 'Configuración', path: '/configuracion' },
  ];

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <aside 
        className="w-64 text-white flex flex-col shadow-lg"
        style={{ backgroundColor: '#2563EB' }}
      >
        {/* Logo */}
        <div 
          className="p-6"
          style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}
        >
          <h1 className="text-2xl font-bold text-white">Las Africanas</h1>
          <p className="text-sm text-blue-100 mt-1">Sistema Integrado</p>
        </div>

        {/* Menu */}
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {menuItems.map((item) => (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors text-left text-white hover:bg-blue-700"
            >
              {item.icon}
              <span className="font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* User info */}
        <div 
          className="p-4"
          style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)' }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div 
              className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ backgroundColor: '#1e40af' }}
            >
              <span className="text-lg font-bold text-white">
                {user?.username.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1">
              <p className="font-semibold text-white">{user?.username}</p>
              <p className="text-sm text-blue-100">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-4 py-2 rounded-lg transition-colors text-white hover:bg-blue-700"
          >
            <LogOut size={20} />
            <span>Cerrar Sesión</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}