import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BarChart3,
  Boxes,
  ClipboardList,
  DollarSign,
  Package,
  ShoppingCart,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react';
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
  const isAdmin = user?.role?.toLowerCase() === 'admin';

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

  const adminStats = [
    {
      icon: <DollarSign className="w-8 h-8 text-emerald-600" />,
      title: 'Ventas hoy',
      value: loading
        ? '...'
        : formatCurrency(ventasStats?.total_facturado ?? 0),
      description: 'Facturación diaria',
    },
    {
      icon: <TrendingUp className="w-8 h-8 text-indigo-600" />,
      title: 'Transacciones',
      value: loading ? '...' : ventasStats?.total_ventas?.toString() ?? '--',
      description: 'Total de comprobantes',
    },
    {
      icon: <Boxes className="w-8 h-8 text-blue-600" />,
      title: 'Valor inventario',
      value: loading
        ? '...'
        : formatCurrency(inventarioStats?.valor_inventario ?? null),
      description: 'Costo total estimado',
    },
    {
      icon: <Package className="w-8 h-8 text-slate-600" />,
      title: 'Productos',
      value: loading ? '...' : inventarioStats?.total?.toString() ?? '--',
      description: 'En catálogo',
    },
    {
      icon: <TriangleAlert className="w-8 h-8 text-orange-600" />,
      title: 'Stock bajo',
      value: loading ? '...' : inventarioStats?.stock_bajo?.toString() ?? '--',
      description: 'Requieren reposición',
    },
    {
      icon: <AlertCircle className="w-8 h-8 text-red-600" />,
      title: 'Agotados',
      value: loading ? '...' : inventarioStats?.agotados?.toString() ?? '--',
      description: 'Sin existencias',
    },
  ];

  const adminPipeline = [
    {
      label: 'Cotizaciones',
      value: ventasStats?.total_cotizaciones ?? 0,
      color: 'bg-blue-100 text-blue-700',
    },
    {
      label: 'Remisiones',
      value: ventasStats?.total_remisiones ?? 0,
      color: 'bg-amber-100 text-amber-700',
    },
    {
      label: 'Facturas',
      value: ventasStats?.total_facturas ?? 0,
      color: 'bg-emerald-100 text-emerald-700',
    },
  ];

  const adminAlerts = [
    {
      label: 'Stock bajo',
      value: inventarioStats?.stock_bajo ?? 0,
    },
    {
      label: 'Productos agotados',
      value: inventarioStats?.agotados ?? 0,
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
        <p className="text-sm text-gray-500">
          {isAdmin
            ? 'Resumen ejecutivo con indicadores clave del negocio.'
            : 'Panel operativo para enfocarte en lo urgente del día.'}
        </p>
        {errorMessage ? (
          <p className="text-sm text-red-600 mt-2">{errorMessage}</p>
        ) : null}
      </div>

      {isAdmin ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {adminStats.map((stat, index) => (
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

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6 xl:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    Panel gerencial
                  </h2>
                  <p className="text-sm text-gray-500">
                    Flujo de ventas del día y visión rápida de facturación.
                  </p>
                </div>
                <BarChart3 className="w-6 h-6 text-blue-600" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {adminPipeline.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-lg border border-gray-100 p-4"
                  >
                    <span
                      className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${item.color}`}
                    >
                      {item.label}
                    </span>
                    <p className="text-2xl font-semibold text-gray-900 mt-3">
                      {loading ? '...' : item.value}
                    </p>
                    <p className="text-sm text-gray-500">
                      Comprobantes registrados
                    </p>
                  </div>
                ))}
              </div>
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="text-sm text-gray-600">
                    Facturación por facturas
                  </p>
                  <p className="text-2xl font-semibold text-gray-900 mt-2">
                    {loading
                      ? '...'
                      : formatCurrency(
                          ventasStats?.total_facturas_valor ??
                            ventasStats?.total_facturado ??
                            0
                        )}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="text-sm text-gray-600">
                    Facturación por remisiones
                  </p>
                  <p className="text-2xl font-semibold text-gray-900 mt-2">
                    {loading
                      ? '...'
                      : formatCurrency(ventasStats?.total_remisiones_valor ?? 0)}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Alertas críticas
                </h2>
                <AlertCircle className="w-6 h-6 text-red-600" />
              </div>
              <div className="space-y-4">
                {adminAlerts.every((item) => item.value === 0) ? (
                  <div className="rounded-lg bg-emerald-50 p-4 text-emerald-700 text-sm">
                    Sin alertas críticas por ahora.
                  </div>
                ) : (
                  adminAlerts.map((alert) => (
                    <div
                      key={alert.label}
                      className="flex items-center justify-between rounded-lg border border-gray-100 p-4"
                    >
                      <div>
                        <p className="text-sm text-gray-600">{alert.label}</p>
                        <p className="text-xl font-semibold text-gray-900 mt-1">
                          {loading ? '...' : alert.value}
                        </p>
                      </div>
                      <TriangleAlert className="w-5 h-5 text-orange-500" />
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6 lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Acciones gerenciales
                </h2>
                <ClipboardList className="w-6 h-6 text-blue-600" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[
                  'Aprobar descuentos pendientes',
                  'Revisar stock crítico',
                  'Analizar ventas por canal',
                  'Programar reposiciones clave',
                ].map((action) => (
                  <button
                    key={action}
                    className="w-full text-left px-4 py-3 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Enfoque del día
              </h2>
              <div className="space-y-3">
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="text-sm text-gray-600">Objetivo de facturación</p>
                  <p className="text-2xl font-semibold text-gray-900 mt-2">
                    {loading
                      ? '...'
                      : formatCurrency(ventasStats?.total_facturado ?? 0)}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 p-4">
                  <p className="text-sm text-gray-600">Productos críticos</p>
                  <p className="text-2xl font-semibold text-gray-900 mt-2">
                    {loading ? '...' : inventarioStats?.stock_bajo ?? 0}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Prioridades operativas
                </h2>
                <ClipboardList className="w-6 h-6 text-blue-600" />
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg border border-gray-100 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Reposiciones urgentes</p>
                    <p className="text-xl font-semibold text-gray-900 mt-1">
                      {loading ? '...' : inventarioStats?.stock_bajo ?? 0}
                    </p>
                  </div>
                  <TriangleAlert className="w-5 h-5 text-orange-500" />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-gray-100 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Productos agotados</p>
                    <p className="text-xl font-semibold text-gray-900 mt-1">
                      {loading ? '...' : inventarioStats?.agotados ?? 0}
                    </p>
                  </div>
                  <AlertCircle className="w-5 h-5 text-red-500" />
                </div>
                <div className="flex items-center justify-between rounded-lg border border-gray-100 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Comprobantes del día</p>
                    <p className="text-xl font-semibold text-gray-900 mt-1">
                      {loading ? '...' : ventasStats?.total_ventas ?? 0}
                    </p>
                  </div>
                  <ShoppingCart className="w-5 h-5 text-green-600" />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  Atajos rápidos
                </h2>
                <BarChart3 className="w-6 h-6 text-blue-600" />
              </div>
              <div className="grid grid-cols-1 gap-3">
                {[
                  'Registrar producto',
                  'Crear venta',
                  'Consultar stock',
                  'Buscar cliente',
                ].map((shortcut) => (
                  <button
                    key={shortcut}
                    className="w-full text-left px-4 py-3 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors"
                  >
                    {shortcut}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Resumen de ventas
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg bg-slate-50 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Facturación del día</p>
                    <p className="text-2xl font-semibold text-gray-900 mt-2">
                      {loading
                        ? '...'
                        : formatCurrency(ventasStats?.total_facturado ?? 0)}
                    </p>
                  </div>
                  <DollarSign className="w-6 h-6 text-emerald-600" />
                </div>
                <div className="flex items-center justify-between rounded-lg bg-slate-50 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Facturas emitidas</p>
                    <p className="text-2xl font-semibold text-gray-900 mt-2">
                      {loading ? '...' : ventasStats?.total_facturas ?? 0}
                    </p>
                  </div>
                  <TrendingUp className="w-6 h-6 text-indigo-600" />
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Estado del inventario
              </h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg bg-slate-50 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Productos activos</p>
                    <p className="text-2xl font-semibold text-gray-900 mt-2">
                      {loading ? '...' : inventarioStats?.total ?? 0}
                    </p>
                  </div>
                  <Package className="w-6 h-6 text-blue-600" />
                </div>
                <div className="flex items-center justify-between rounded-lg bg-slate-50 p-4">
                  <div>
                    <p className="text-sm text-gray-600">Valor del inventario</p>
                    <p className="text-2xl font-semibold text-gray-900 mt-2">
                      {loading
                        ? '...'
                        : formatCurrency(inventarioStats?.valor_inventario ?? null)}
                    </p>
                  </div>
                  <Boxes className="w-6 h-6 text-slate-600" />
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
