import { useState, useEffect } from "react";
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
  Edit,
  Trash2,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import {
  configuracionEmpresaApi,
  impuestosApi,
  auditoriaApi,
  usuariosApi,
  backupApi,
  type ConfiguracionEmpresa as ConfiguracionEmpresaType,
  type Impuesto,
  type Auditoria,
  type Usuario,
  type Backup,
} from "../api/configuracion";

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
  const [formData, setFormData] = useState<ConfiguracionEmpresaType>({
    tipo_identificacion: "NIT",
    identificacion: "",
    dv: "",
    tipo_persona: "Persona natural",
    razon_social: "",
    regimen: "RÉGIMEN COMÚN",
    direccion: "",
    ciudad: "",
    municipio: "",
    telefono: "",
    sitio_web: "",
    correo: "",
  });

  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [logoFile, setLogoFile] = useState<File | null>(null);

  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      setCargando(true);
      const data = await configuracionEmpresaApi.obtener();
      setFormData(data);
    } catch (error) {
      console.error("Error al cargar configuración:", error);
      alert("Error al cargar los datos de la empresa");
    } finally {
      setCargando(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardando(true);

    try {
      if (formData.id) {
        await configuracionEmpresaApi.actualizar(formData.id, formData);

        // Si hay un logo seleccionado, subirlo
        if (logoFile) {
          await configuracionEmpresaApi.subirLogo(formData.id, logoFile);
          setLogoFile(null);
        }

        alert("Datos de empresa guardados exitosamente");
        await cargarDatos();
      }
    } catch (error) {
      console.error("Error al guardar:", error);
      alert("Error al guardar los datos de la empresa");
    } finally {
      setGuardando(false);
    }
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setLogoFile(e.target.files[0]);
    }
  };

  const handleCancel = () => {
    cargarDatos();
    setLogoFile(null);
  };

  if (cargando) {
    return (
      <div className="p-6 flex items-center justify-center">
        <p className="text-gray-600">Cargando...</p>
      </div>
    );
  }

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
                <div className="w-32 h-32 border-2 border-dashed border-gray-300 rounded flex items-center justify-center bg-gray-50 overflow-hidden">
                  {formData.logo ? (
                    <img
                      src={formData.logo}
                      alt="Logo"
                      className="w-full h-full object-contain"
                    />
                  ) : logoFile ? (
                    <span className="text-gray-600 text-sm text-center px-2">
                      {logoFile.name}
                    </span>
                  ) : (
                    <span className="text-gray-400 text-sm">Sin logo</span>
                  )}
                </div>
                <input
                  type="file"
                  id="logo-input"
                  accept="image/*"
                  onChange={handleLogoChange}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => document.getElementById("logo-input")?.click()}
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
              className="px-6 py-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded flex items-center gap-2 font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save size={18} />
              {guardando ? "GUARDANDO..." : "GUARDAR"}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              disabled={guardando}
              className="px-6 py-2 bg-red-100 hover:bg-red-200 border border-red-400 rounded flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
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
  const [impuestos, setImpuestos] = useState<Impuesto[]>([]);
  const [nuevoValor, setNuevoValor] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    cargarImpuestos();
  }, []);

  const cargarImpuestos = async () => {
    try {
      setCargando(true);
      const data = await impuestosApi.listar();
      setImpuestos(data);
    } catch (error) {
      console.error("Error al cargar impuestos:", error);
      alert("Error al cargar los impuestos");
    } finally {
      setCargando(false);
    }
  };

  const handleAgregarImpuesto = async () => {
    if (!nuevoValor.trim()) {
      alert("Por favor ingrese un valor");
      return;
    }

    setGuardando(true);
    try {
      const esExento = nuevoValor.toUpperCase() === "E";
      const porcentaje = esExento ? 0 : parseFloat(nuevoValor);

      if (!esExento && isNaN(porcentaje)) {
        alert("Valor inválido. Ingrese un número o 'E' para exento");
        return;
      }

      await impuestosApi.crear({
        nombre: "IVA",
        valor: nuevoValor.toUpperCase(),
        porcentaje: esExento ? 0 : porcentaje,
        es_exento: esExento,
        is_active: true,
      });

      setNuevoValor("");
      await cargarImpuestos();
    } catch (error) {
      console.error("Error al agregar impuesto:", error);
      alert("Error al agregar el impuesto");
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) {
    return (
      <div className="p-6 flex items-center justify-center">
        <p className="text-gray-600">Cargando...</p>
      </div>
    );
  }

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
            value={nuevoValor}
            onChange={(e) => setNuevoValor(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleAgregarImpuesto()}
            placeholder="19 o E"
            disabled={guardando}
            className="w-24 px-3 py-2 border border-gray-300 rounded disabled:opacity-50"
          />
          <button
            onClick={handleAgregarImpuesto}
            disabled={guardando}
            className="p-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded w-10 h-10 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
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
  const [auditorias, setAuditorias] = useState<Auditoria[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    cargarAuditorias();
  }, []);

  const cargarAuditorias = async () => {
    try {
      setCargando(true);
      const data = await auditoriaApi.listar();
      setAuditorias(data);
    } catch (error) {
      console.error("Error al cargar auditorías:", error);
      alert("Error al cargar las auditorías");
    } finally {
      setCargando(false);
    }
  };

  const formatearFecha = (fecha: string) => {
    const date = new Date(fecha);
    return date.toLocaleString("es-CO", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (cargando) {
    return (
      <div className="p-6 flex items-center justify-center">
        <p className="text-gray-600">Cargando...</p>
      </div>
    );
  }

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
              {auditorias.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                    No hay registros de auditoría
                  </td>
                </tr>
              ) : (
                auditorias.map((aud, index) => (
                  <tr
                    key={aud.id}
                    className={index % 2 === 0 ? "bg-blue-50" : "bg-white"}
                  >
                    <td className="px-4 py-2 text-sm border-r border-gray-200">
                      {formatearFecha(aud.fecha_hora)}
                    </td>
                    <td className="px-4 py-2 text-sm border-r border-gray-200">
                      {aud.usuario_nombre}
                    </td>
                    <td className="px-4 py-2 text-sm border-r border-gray-200">
                      {aud.accion}
                    </td>
                    <td className="px-4 py-2 text-sm">{aud.notas}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ConfiguracionUsuarios() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [cargando, setCargando] = useState(true);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [usuarioEditando, setUsuarioEditando] = useState<Usuario | null>(null);

  useEffect(() => {
    cargarUsuarios();
  }, []);

  const cargarUsuarios = async () => {
    try {
      setCargando(true);
      const data = await usuariosApi.listar();
      setUsuarios(data);
    } catch (error) {
      console.error("Error al cargar usuarios:", error);
      alert("Error al cargar los usuarios");
    } finally {
      setCargando(false);
    }
  };

  const handleDesactivar = async (usuario: Usuario) => {
    if (
      !confirm(
        `¿Está seguro de desactivar al usuario ${usuario.username}?`
      )
    ) {
      return;
    }

    try {
      if (usuario.id) {
        await usuariosApi.desactivar(usuario.id);
        await cargarUsuarios();
      }
    } catch (error) {
      console.error("Error al desactivar usuario:", error);
      alert("Error al desactivar el usuario");
    }
  };

  const handleEditar = (usuario: Usuario) => {
    setUsuarioEditando(usuario);
    setMostrarModal(true);
  };

  const handleNuevo = () => {
    setUsuarioEditando(null);
    setMostrarModal(true);
  };

  if (cargando) {
    return (
      <div className="p-6 flex items-center justify-center">
        <p className="text-gray-600">Cargando...</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          Gestión de Usuarios
        </h1>
        <button
          onClick={handleNuevo}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
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
                NOMBRE
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                ROL
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
            {usuarios.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                  No hay usuarios registrados
                </td>
              </tr>
            ) : (
              usuarios.map((usuario) => (
                <tr key={usuario.id}>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.username}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.nombre_completo || `${usuario.first_name} ${usuario.last_name}`}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.tipo_usuario}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 text-xs font-semibold rounded-full ${
                        usuario.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {usuario.is_active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right text-sm space-x-2">
                    <button
                      onClick={() => handleEditar(usuario)}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      Editar
                    </button>
                    {usuario.is_active && (
                      <button
                        onClick={() => handleDesactivar(usuario)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Desactivar
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {mostrarModal && (
        <ModalUsuario
          usuario={usuarioEditando}
          onClose={() => {
            setMostrarModal(false);
            setUsuarioEditando(null);
          }}
          onGuardar={cargarUsuarios}
        />
      )}
    </div>
  );
}

function ModalUsuario({
  usuario,
  onClose,
  onGuardar,
}: {
  usuario: Usuario | null;
  onClose: () => void;
  onGuardar: () => void;
}) {
  const [formData, setFormData] = useState<Partial<Usuario>>({
    username: usuario?.username || "",
    email: usuario?.email || "",
    first_name: usuario?.first_name || "",
    last_name: usuario?.last_name || "",
    tipo_usuario: usuario?.tipo_usuario || "Vendedor",
    telefono: usuario?.telefono || "",
    sede: usuario?.sede || "",
    password: "",
  });
  const [guardando, setGuardando] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardando(true);

    try {
      if (usuario?.id) {
        // Actualizar usuario existente
        const dataToUpdate = { ...formData };
        if (!dataToUpdate.password) {
          delete dataToUpdate.password;
        }
        await usuariosApi.actualizar(usuario.id, dataToUpdate);
      } else {
        // Crear nuevo usuario
        if (!formData.password) {
          alert("La contraseña es obligatoria para usuarios nuevos");
          setGuardando(false);
          return;
        }
        await usuariosApi.crear(formData);
      }

      onGuardar();
      onClose();
    } catch (error) {
      console.error("Error al guardar usuario:", error);
      alert("Error al guardar el usuario");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4">
          {usuario ? "Editar Usuario" : "Nuevo Usuario"}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Usuario
              </label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) =>
                  setFormData({ ...formData, username: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nombre
              </label>
              <input
                type="text"
                value={formData.first_name}
                onChange={(e) =>
                  setFormData({ ...formData, first_name: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Apellido
              </label>
              <input
                type="text"
                value={formData.last_name}
                onChange={(e) =>
                  setFormData({ ...formData, last_name: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tipo de Usuario
              </label>
              <select
                value={formData.tipo_usuario}
                onChange={(e) =>
                  setFormData({ ...formData, tipo_usuario: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="Administrador">Administrador</option>
                <option value="Vendedor">Vendedor</option>
                <option value="Mecanico">Mecánico</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Teléfono
              </label>
              <input
                type="text"
                value={formData.telefono}
                onChange={(e) =>
                  setFormData({ ...formData, telefono: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Sede
              </label>
              <input
                type="text"
                value={formData.sede}
                onChange={(e) =>
                  setFormData({ ...formData, sede: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contraseña {usuario && "(dejar vacío para no cambiar)"}
              </label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                required={!usuario}
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              disabled={guardando}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={guardando}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {guardando ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </form>
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
  const [guardando, setGuardando] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.clave_nueva !== formData.confirmar_clave) {
      alert("Las contraseñas no coinciden");
      return;
    }

    if (formData.clave_nueva.length < 6) {
      alert("La contraseña debe tener al menos 6 caracteres");
      return;
    }

    setGuardando(true);
    try {
      await usuariosApi.cambiarPassword(formData);
      alert("Contraseña cambiada exitosamente");
      setFormData({ clave_actual: "", clave_nueva: "", confirmar_clave: "" });
    } catch (error: any) {
      console.error("Error al cambiar contraseña:", error);
      const mensaje = error.response?.data?.clave_actual?.[0] ||
                      error.response?.data?.clave_nueva?.[0] ||
                      "Error al cambiar la contraseña";
      alert(mensaje);
    } finally {
      setGuardando(false);
    }
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
              disabled={guardando}
              className="w-full px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {guardando ? "Cambiando..." : "Cambiar Contraseña"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function BackupRestore() {
  const [backups, setBackups] = useState<Backup[]>([]);
  const [cargando, setCargando] = useState(true);
  const [creandoBackup, setCreandoBackup] = useState(false);

  useEffect(() => {
    cargarBackups();
  }, []);

  const cargarBackups = async () => {
    try {
      setCargando(true);
      const data = await backupApi.listarBackups();
      setBackups(data);
    } catch (error) {
      console.error("Error al cargar backups:", error);
      alert("Error al cargar la lista de backups");
    } finally {
      setCargando(false);
    }
  };

  const handleCrearBackup = async () => {
    if (!confirm("¿Está seguro de crear un backup de la base de datos?")) {
      return;
    }

    setCreandoBackup(true);
    try {
      const resultado = await backupApi.crearBackup();
      alert(`Backup creado exitosamente: ${resultado.archivo}`);
      await cargarBackups();
    } catch (error) {
      console.error("Error al crear backup:", error);
      alert("Error al crear el backup");
    } finally {
      setCreandoBackup(false);
    }
  };

  const formatearTamaño = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  };

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
          <button
            onClick={handleCrearBackup}
            disabled={creandoBackup}
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {creandoBackup ? "Creando Backup..." : "Crear Backup Ahora"}
          </button>
        </div>

        {/* Restaurar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-xl font-semibold mb-4">Restaurar desde Backup</h3>
          <p className="text-sm text-gray-600 mb-4">
            Restaura la base de datos desde un archivo de backup
          </p>
          <p className="text-sm text-yellow-600 mb-4">
            Nota: La función de restauración debe implementarse con precaución.
            Contacte al administrador del sistema.
          </p>
        </div>

        {/* Backups Anteriores */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-xl font-semibold mb-4">Backups Anteriores</h3>
          {cargando ? (
            <div className="text-center text-gray-500 py-8">Cargando...</div>
          ) : backups.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              No hay backups disponibles
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Archivo
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Fecha
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Tamaño
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {backups.map((backup, index) => (
                    <tr key={index}>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {backup.nombre}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {backup.fecha}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {formatearTamaño(backup.tamaño)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
