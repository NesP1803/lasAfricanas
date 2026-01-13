import { useState } from "react";
import {
  Building2,
  Users,
  FileText,
  Percent,
  ClipboardList,
  Key,
  Database,
  Settings as SettingsIcon,
  HelpCircle,
  Save,
  X,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

type SeccionConfig =
  | "empresa"
  | "usuarios"
  | "facturacion"
  | "impuestos"
  | "auditoria"
  | "cambiar-clave"
  | "backup";

export default function Configuracion() {
  const { user } = useAuth();
  const [seccionActiva, setSeccionActiva] = useState<SeccionConfig>("empresa");

  return (
    <div className="h-full flex bg-gray-50">
      {/* Sidebar de Configuración */}
      <div className="w-64 bg-white border-r border-gray-300 shadow-sm">
        <div className="p-4 border-b border-gray-300 bg-gray-100">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <SettingsIcon size={20} />
            Configuración
          </h2>
        </div>

        <nav className="p-2">
          <MenuItem
            icon={<Building2 size={18} />}
            label="Empresa"
            active={seccionActiva === "empresa"}
            onClick={() => setSeccionActiva("empresa")}
          />
          <MenuItem
            icon={<Users size={18} />}
            label="Usuarios"
            active={seccionActiva === "usuarios"}
            onClick={() => setSeccionActiva("usuarios")}
          />
          <MenuItem
            icon={<FileText size={18} />}
            label="Facturación"
            active={seccionActiva === "facturacion"}
            onClick={() => setSeccionActiva("facturacion")}
          />
          <MenuItem
            icon={<Percent size={18} />}
            label="Impuestos"
            active={seccionActiva === "impuestos"}
            onClick={() => setSeccionActiva("impuestos")}
          />
          <MenuItem
            icon={<ClipboardList size={18} />}
            label="Auditoría"
            active={seccionActiva === "auditoria"}
            onClick={() => setSeccionActiva("auditoria")}
          />

          <div className="my-2 border-t border-gray-300"></div>

          <MenuItem
            icon={<Key size={18} />}
            label="Cambiar Clave"
            active={seccionActiva === "cambiar-clave"}
            onClick={() => setSeccionActiva("cambiar-clave")}
          />
          <MenuItem
            icon={<Database size={18} />}
            label="Backup/Restaurar"
            active={seccionActiva === "backup"}
            onClick={() => setSeccionActiva("backup")}
          />
        </nav>
      </div>

      {/* Contenido Principal */}
      <div className="flex-1 overflow-y-auto">
        {seccionActiva === "empresa" && <ConfiguracionEmpresa />}
        {seccionActiva === "usuarios" && <ConfiguracionUsuarios />}
        {seccionActiva === "facturacion" && <ConfiguracionFacturacion />}
        {seccionActiva === "impuestos" && <ConfiguracionImpuestos />}
        {seccionActiva === "auditoria" && <ConfiguracionAuditoria />}
        {seccionActiva === "cambiar-clave" && <CambiarClave />}
        {seccionActiva === "backup" && <BackupRestore />}
      </div>
    </div>
  );
}

function MenuItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-colors ${
        active ? "bg-blue-600 text-white" : "text-gray-700 hover:bg-gray-100"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

// ============================================
// SECCIÓN: EMPRESA (Estilo SIDEFA)
// ============================================
function ConfiguracionEmpresa() {
  const [formData, setFormData] = useState({
    tipo_identificacion: "NIT",
    identificacion: "91068915",
    dv: "8",
    tipo_persona: "Persona natural",
    razon_social: "MOTOREPUESTOS LAS AFRICANAS",
    regimen: "RÉGIMEN COMÚN",
    direccion: "CALLE 6 # 12A-45 GAIRA",
    ciudad: "MAGDALENA",
    municipio: "SANTA MARTA",
    telefono: "54350548",
    sitio_web: "",
    correo: "",
  });

  const [guardando, setGuardando] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardando(true);

    setTimeout(() => {
      alert("Datos de empresa guardados");
      setGuardando(false);
    }, 1000);
  };

  return (
    <div className="p-6">
      <div className="bg-blue-100 border border-blue-300 rounded-md p-3 mb-6">
        <h2 className="text-lg font-bold text-blue-900">
          ACTUALIZA LOS DATOS GENERALES DE TU EMPRESA
        </h2>
      </div>

      <div className="bg-white border border-gray-300 rounded-md shadow-sm">
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Tipo de identificación */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Tipo de identificación
              </label>
              <div className="flex-1 flex items-center gap-2">
                <select
                  value={formData.tipo_identificacion}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      tipo_identificacion: e.target.value,
                    })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="NIT">
                    NÚMERO DE IDENTIFICACIÓN TRIBUTARIA (NIT)
                  </option>
                  <option value="CC">CÉDULA DE CIUDADANÍA</option>
                  <option value="CE">CÉDULA DE EXTRANJERÍA</option>
                </select>
              </div>
            </div>

            {/* Identificación */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Identificación
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={formData.identificacion}
                  onChange={(e) =>
                    setFormData({ ...formData, identificacion: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <label className="text-sm font-medium">DV</label>
                <input
                  type="text"
                  value={formData.dv}
                  onChange={(e) =>
                    setFormData({ ...formData, dv: e.target.value })
                  }
                  className="w-16 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  maxLength={1}
                />
              </div>
            </div>

            {/* Tipo de persona */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Tipo de persona
              </label>
              <div className="flex-1 flex items-center gap-2">
                <select
                  value={formData.tipo_persona}
                  onChange={(e) =>
                    setFormData({ ...formData, tipo_persona: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="Persona natural">Persona natural</option>
                  <option value="Persona jurídica">Persona jurídica</option>
                </select>
              </div>
            </div>

            {/* Razón Social */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Razón Social
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={formData.razon_social}
                  onChange={(e) =>
                    setFormData({ ...formData, razon_social: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Régimen */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Régimen
              </label>
              <div className="flex-1 flex items-center gap-2">
                <select
                  value={formData.regimen}
                  onChange={(e) =>
                    setFormData({ ...formData, regimen: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="RÉGIMEN COMÚN">RÉGIMEN COMÚN</option>
                  <option value="RÉGIMEN SIMPLIFICADO">
                    RÉGIMEN SIMPLIFICADO
                  </option>
                </select>
              </div>
            </div>

            {/* Dirección */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Dirección
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={formData.direccion}
                  onChange={(e) =>
                    setFormData({ ...formData, direccion: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Ciudad y Municipio */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right"></label>
              <div className="flex-1 flex items-center gap-2">
                <select
                  value={formData.ciudad}
                  onChange={(e) =>
                    setFormData({ ...formData, ciudad: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="MAGDALENA">MAGDALENA</option>
                  <option value="ATLÁNTICO">ATLÁNTICO</option>
                  <option value="CESAR">CESAR</option>
                </select>
                <input
                  type="text"
                  value={formData.municipio}
                  onChange={(e) =>
                    setFormData({ ...formData, municipio: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Teléfono */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Teléfono
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={formData.telefono}
                  onChange={(e) =>
                    setFormData({ ...formData, telefono: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Sitio web */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Sitio web
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="text"
                  value={formData.sitio_web}
                  onChange={(e) =>
                    setFormData({ ...formData, sitio_web: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Correo */}
            <div className="col-span-2 flex items-center gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right">
                Correo
              </label>
              <div className="flex-1 flex items-center gap-2">
                <input
                  type="email"
                  value={formData.correo}
                  onChange={(e) =>
                    setFormData({ ...formData, correo: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Logo */}
            <div className="col-span-2 flex items-start gap-4">
              <label className="w-48 text-sm font-medium text-gray-700 text-right pt-2">
                Logo
              </label>
              <div className="flex-1 flex items-start gap-2">
                <div className="w-32 h-32 border-2 border-dashed border-gray-300 rounded flex items-center justify-center bg-gray-50">
                  <span className="text-gray-400 text-sm">Sin logo</span>
                </div>
                <button
                  type="button"
                  className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded border border-gray-400"
                >
                  📁 Seleccionar
                </button>
              </div>
            </div>
          </div>

          {/* Botones */}
          <div className="flex justify-start gap-3 pt-4 border-t border-gray-300">
            <button
              type="submit"
              disabled={guardando}
              className="px-6 py-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded flex items-center gap-2 font-semibold"
            >
              <Save size={18} />
              {guardando ? "GUARDANDO..." : "GUARDAR"}
            </button>
            <button
              type="button"
              className="px-6 py-2 bg-red-100 hover:bg-red-200 border border-red-400 rounded flex items-center gap-2"
            >
              <X size={18} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: FACTURACIÓN (Estilo SIDEFA)
// ============================================
function ConfiguracionFacturacion() {
  const [config, setConfig] = useState({
    prefijo_factura: "FAC",
    numero_factura: "100702",
    ultima_factura: "100701",
    prefijo_remision: "",
    numero_remision: "154239",
    ultima_remision: "154238",
    resolucion: "18764006081459 de 2020/10/22\nRango del 00001 al 50000",
    notas_factura:
      "Para trámite de cambios y garantías. Indispensable presentar la factura de venta. Tiene hasta 5 días para trámites. Las Partes Eléctricas No Tiene Devolución. Los productos deben estar en perfecto estado y empaque original.",
  });

  return (
    <div className="p-6">
      <div className="bg-white border border-gray-300 rounded-md shadow-sm p-6 max-w-2xl">
        <h2 className="text-lg font-bold text-red-700 mb-6 border-b pb-2">
          Numeración para facturas de venta.
        </h2>

        {/* Facturas */}
        <div className="mb-6">
          <p className="text-sm font-semibold text-red-700 mb-3">
            Indica los datos con el cual vas a crear tus próximas facturas.
          </p>
          <div className="flex items-center gap-4 mb-2">
            <label className="w-20 text-sm font-medium">Prefijo</label>
            <input
              type="text"
              value={config.prefijo_factura}
              onChange={(e) =>
                setConfig({ ...config, prefijo_factura: e.target.value })
              }
              className="w-24 px-3 py-2 border border-gray-300 rounded text-center"
            />

            <label className="text-sm font-medium">Número</label>
            <input
              type="text"
              value={config.numero_factura}
              onChange={(e) =>
                setConfig({ ...config, numero_factura: e.target.value })
              }
              className="w-32 px-3 py-2 border border-gray-300 rounded"
            />
          </div>
          <p className="text-sm text-gray-600 ml-24">
            Última factura generada {config.prefijo_factura}{" "}
            {config.ultima_factura}
          </p>
        </div>

        {/* Remisiones */}
        <div className="mb-6">
          <p className="text-sm font-semibold text-red-700 mb-3">
            Indica los datos con el cual vas a crear tus próximas remisiones.
          </p>
          <div className="flex items-center gap-4 mb-2">
            <label className="w-20 text-sm font-medium">Número</label>
            <input
              type="text"
              value={config.numero_remision}
              onChange={(e) =>
                setConfig({ ...config, numero_remision: e.target.value })
              }
              className="w-32 px-3 py-2 border border-gray-300 rounded"
            />
          </div>
          <p className="text-sm text-gray-600 ml-24">
            Última remisión generada {config.ultima_remision}
          </p>
        </div>

        {/* Resolución */}
        <div className="mb-6">
          <div className="flex items-start gap-2 mb-2">
            <label className="text-sm font-medium">Resolución.</label>
          </div>
          <textarea
            value={config.resolucion}
            onChange={(e) =>
              setConfig({ ...config, resolucion: e.target.value })
            }
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded"
          />
        </div>

        {/* Notas de factura */}
        <div className="mb-6">
          <div className="flex items-start gap-2 mb-2">
            <label className="text-sm font-medium">
              Notas de la factura de venta.
            </label>
          </div>
          <textarea
            value={config.notas_factura}
            onChange={(e) =>
              setConfig({ ...config, notas_factura: e.target.value })
            }
            rows={5}
            className="w-full px-3 py-2 border border-gray-300 rounded"
          />
        </div>

        {/* Botones */}
        <div className="flex justify-center gap-3 pt-4 border-t border-gray-300">
          <button className="px-6 py-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded flex items-center gap-2 font-semibold">
            <Save size={18} />
            GUARDAR
          </button>
          <button className="px-6 py-2 bg-red-100 hover:bg-red-200 border border-red-400 rounded flex items-center gap-2">
            <X size={18} />
            CERRAR
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: IMPUESTOS (Estilo SIDEFA)
// ============================================
function ConfiguracionImpuestos() {
  const [impuestos, setImpuestos] = useState([
    { id: 1, nombre: "IVA", valor: "0" },
    { id: 2, nombre: "", valor: "19" },
    { id: 3, nombre: "", valor: "E" },
  ]);

  return (
    <div className="p-6">
      <div className="bg-white border border-gray-300 rounded-md shadow-sm p-6 max-w-md">
        <h2 className="text-lg font-bold mb-4">Impuestos</h2>

        <table className="w-full mb-4">
          <thead>
            <tr className="bg-blue-100">
              <th className="border border-gray-300 px-4 py-2 text-left">
                IVA
              </th>
            </tr>
          </thead>
          <tbody>
            {impuestos.map((imp) => (
              <tr key={imp.id} className="hover:bg-gray-50">
                <td className="border border-gray-300 px-4 py-2">
                  <input
                    type="text"
                    value={imp.valor}
                    readOnly
                    className="w-full px-2 py-1 border-0 focus:ring-0 bg-gray-100 cursor-not-allowed"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="flex justify-center gap-3">
          <input
            type="text"
            className="w-24 px-3 py-2 border border-gray-300 rounded"
          />
          <button className="p-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded w-10 h-10 flex items-center justify-center">
            <Save size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: AUDITORÍA (Estilo SIDEFA)
// ============================================
function ConfiguracionAuditoria() {
  const auditorias = [
    {
      fecha: "22/10/2025 20:09",
      usuario: "jorge",
      accion: "Eliminar",
      notas: "Se elimino moto : NKD - FABIAN RAMIREZ",
    },
    {
      fecha: "22/10/2025 20:06",
      usuario: "jorge",
      accion: "Actualizar",
      notas: "Se Actualizo un articulo : ACEITE 20W",
    },
    {
      fecha: "22/10/2025 19:53",
      usuario: "jorge",
      accion: "Actualizar",
      notas: "Se Actualizo un articulo : MANUBRIO",
    },
  ];

  return (
    <div className="p-6">
      <div className="bg-white border border-gray-300 rounded-md shadow-sm">
        <div className="bg-blue-100 px-4 py-2 border-b border-gray-300">
          <h2 className="text-lg font-bold">Auditoría</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-300">
                <th className="px-4 py-2 text-left text-sm font-semibold">
                  fechahora
                </th>
                <th className="px-4 py-2 text-left text-sm font-semibold">
                  usuario
                </th>
                <th className="px-4 py-2 text-left text-sm font-semibold">
                  accion
                </th>
                <th className="px-4 py-2 text-left text-sm font-semibold">
                  notas
                </th>
              </tr>
            </thead>
            <tbody>
              {auditorias.map((aud, index) => (
                <tr
                  key={index}
                  className={index % 2 === 0 ? "bg-blue-50" : "bg-white"}
                >
                  <td className="px-4 py-2 text-sm border-r border-gray-200">
                    {aud.fecha}
                  </td>
                  <td className="px-4 py-2 text-sm border-r border-gray-200">
                    {aud.usuario}
                  </td>
                  <td className="px-4 py-2 text-sm border-r border-gray-200">
                    {aud.accion}
                  </td>
                  <td className="px-4 py-2 text-sm">{aud.notas}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Las secciones de Usuarios, Cambiar Clave y Backup se mantienen igual...
// (Continúa en el siguiente mensaje)

function ConfiguracionUsuarios() {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          Gestión de Usuarios
        </h1>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          + Nuevo Usuario
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                USUARIO
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                ROL
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                DESCUENTO MÁX.
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                ESTADO
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                ACCIONES
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            <tr>
              <td className="px-6 py-4 text-sm text-gray-900">admin</td>
              <td className="px-6 py-4 text-sm text-gray-900">Administrador</td>
              <td className="px-6 py-4 text-sm text-gray-900">100%</td>
              <td className="px-6 py-4">
                <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700">
                  Activo
                </span>
              </td>
              <td className="px-6 py-4 text-right text-sm space-x-2">
                <button className="text-blue-600 hover:text-blue-900">
                  Editar
                </button>
                <button className="text-red-600 hover:text-red-900">
                  Desactivar
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CambiarClave() {
  const [formData, setFormData] = useState({
    clave_actual: "",
    clave_nueva: "",
    confirmar_clave: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.clave_nueva !== formData.confirmar_clave) {
      alert("Las contraseñas no coinciden");
      return;
    }

    alert("Contraseña cambiada exitosamente");
    setFormData({ clave_actual: "", clave_nueva: "", confirmar_clave: "" });
  };

  return (
    <div className="p-6">
      <div className="max-w-md mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">
          Cambiar Contraseña
        </h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contraseña Actual
              </label>
              <input
                type="password"
                value={formData.clave_actual}
                onChange={(e) =>
                  setFormData({ ...formData, clave_actual: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nueva Contraseña
              </label>
              <input
                type="password"
                value={formData.clave_nueva}
                onChange={(e) =>
                  setFormData({ ...formData, clave_nueva: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Confirmar Nueva Contraseña
              </label>
              <input
                type="password"
                value={formData.confirmar_clave}
                onChange={(e) =>
                  setFormData({ ...formData, confirmar_clave: e.target.value })
                }
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
            >
              Cambiar Contraseña
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function BackupRestore() {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">
        Backup y Restauración
      </h1>

      <div className="max-w-4xl space-y-6">
        {/* Crear Backup */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-xl font-semibold mb-4">Crear Backup</h3>
          <p className="text-sm text-gray-600 mb-4">
            Crea una copia de seguridad completa de la base de datos
          </p>
          <button className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium">
            Crear Backup Ahora
          </button>
        </div>

        {/* Restaurar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-xl font-semibold mb-4">Restaurar desde Backup</h3>
          <p className="text-sm text-gray-600 mb-4">
            Restaura la base de datos desde un archivo de backup
          </p>
          <div className="flex items-center gap-4">
            <input
              type="file"
              accept=".sql,.backup"
              className="block flex-1 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
            <button className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">
              Seleccionar archivo
            </button>
          </div>
        </div>

        {/* Backups Anteriores */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-xl font-semibold mb-4">Backups Anteriores</h3>
          <div className="text-center text-gray-500 py-8">
            No hay backups disponibles
          </div>
        </div>
      </div>
    </div>
  );
}
