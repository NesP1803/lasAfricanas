import { useAuth } from '../contexts/AuthContext';
import { Package, ShoppingCart, Users } from 'lucide-react';

export default function Dashboard() {
  const { user } = useAuth();

  const stats = [
    {
      icon: <Package className="w-8 h-8 text-blue-600" />,
      title: 'Productos',
      value: '0',
      description: 'En inventario',
    },
    {
      icon: <ShoppingCart className="w-8 h-8 text-green-600" />,
      title: 'Ventas del día',
      value: '$0',
      description: 'Total de hoy',
    },
    {
      icon: <Users className="w-8 h-8 text-orange-600" />,
      title: 'Clientes',
      value: '0',
      description: 'Registrados',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-2">
          Bienvenido, {user?.username}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <div
            key={index}
            className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm font-medium">
                  {stat.title}
                </p>
                <p className="text-3xl font-bold text-gray-900 mt-2">
                  {stat.value}
                </p>
                <p className="text-gray-500 text-sm mt-1">
                  {stat.description}
                </p>
              </div>
              <div>{stat.icon}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Additional Info */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Actividad Reciente
          </h2>
          <p className="text-gray-600">No hay actividad reciente</p>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Accesos Rápidos
          </h2>
          <div className="space-y-2">
            <button className="w-full text-left px-4 py-2 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors">
              Registrar producto
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
