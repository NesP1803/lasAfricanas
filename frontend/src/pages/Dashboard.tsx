import { Users, Package, Wrench, DollarSign } from 'lucide-react';

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-800">Dashboard</h1>

      {/* Cards de resumen */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Ventas Hoy"
          value="$2,450,000"
          icon={<DollarSign size={32} />}
          color="bg-green-500"
        />
        <StatCard
          title="Productos"
          value="9,549"
          icon={<Package size={32} />}
          color="bg-blue-500"
        />
        <StatCard
          title="Servicios Activos"
          value="12"
          icon={<Wrench size={32} />}
          color="bg-orange-500"
        />
        <StatCard
          title="Clientes"
          value="1,234"
          icon={<Users size={32} />}
          color="bg-purple-500"
        />
      </div>

      {/* Contenido adicional */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="panel-sidefa p-6">
          <h2 className="text-xl font-bold mb-4">Productos con Stock Bajo</h2>
          <p className="text-gray-600">Próximamente...</p>
        </div>

        <div className="panel-sidefa p-6">
          <h2 className="text-xl font-bold mb-4">Servicios Pendientes</h2>
          <p className="text-gray-600">Próximamente...</p>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-600 text-sm">{title}</p>
          <p className="text-2xl font-bold text-gray-800 mt-2">{value}</p>
        </div>
        <div className={`${color} text-white p-3 rounded-lg`}>{icon}</div>
      </div>
    </div>
  );
}