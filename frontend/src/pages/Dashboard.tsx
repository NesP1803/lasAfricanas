import { useEffect, useMemo, useState } from 'react';
import { Package, ShoppingCart, TriangleAlert } from 'lucide-react';
import { inventarioApi, type InventarioEstadisticas } from '../api/inventario';
import { ventasApi, type EstadisticasVentas } from '../api/ventas';
import { useAuth } from '../contexts/AuthContext';

export default function Dashboard() {
  const { user } = useAuth();
  const [inventarioStats, setInventarioStats] =
    useState<InventarioEstadisticas | null>(null);
  const [ventasStats, setVentasStats] = useState<EstadisticasVentas | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0,
      }),
    []
  );

  useEffect(() => {
    let isMounted = true;

    const fetchStats = async () => {
      try {
        setLoading(true);
        setErrorMessage(null);
        const [inventarioResponse, ventasResponse] = await Promise.all([
          inventarioApi.getEstadisticas(),
          ventasApi.getEstadisticasHoy(),
        ]);

        if (!isMounted) return;
        setInventarioStats(inventarioResponse);
        setVentasStats(ventasResponse);
      } catch (error) {
        if (!isMounted) return;
        setErrorMessage('No se pudieron cargar las estadísticas del dashboard.');
      } finally {
        if (!isMounted) return;
        setLoading(false);
      }
    };

    fetchStats();

    return () => {
      isMounted = false;
    };
  }, []);

  const formatCurrency = (value: string | number | null | undefined) => {
    if (value === null || value === undefined) {
      return '--';
    }
    const numericValue = typeof value === 'string' ? Number(value) : value;
    if (Number.isNaN(numericValue)) {
      return '--';
    }
    return currencyFormatter.format(numericValue);
  };

  const stats = [
    {
      icon: <Package className="w-8 h-8 text-blue-600" />,
      title: 'Productos',
      value: loading ? '...' : inventarioStats?.total?.toString() ?? '--',
      description: 'En inventario',
    },
    {
      icon: <ShoppingCart className="w-8 h-8 text-green-600" />,
      title: 'Ventas del día',
      value: loading
        ? '...'
        : formatCurrency(ventasStats?.total_facturado ?? 0),
      description: 'Total de hoy',
    },
    {
      icon: <TriangleAlert className="w-8 h-8 text-orange-600" />,
      title: 'Stock bajo',
      value: loading ? '...' : inventarioStats?.stock_bajo?.toString() ?? '--',
      description: 'Requieren reposición',
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
        {errorMessage ? (
          <p className="text-sm text-red-600 mt-2">{errorMessage}</p>
        ) : null}
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
            Atajos rápidos
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
