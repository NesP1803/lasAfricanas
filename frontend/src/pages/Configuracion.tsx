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
  Save,
  X,
  Edit2,
  Trash2,
  Plus,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import {
  configuracionEmpresaApi,
  impuestosApi,
  auditoriaApi,
  usuariosApi,
  backupApi,
  type ConfiguracionEmpresa as ConfigEmpresaType,
  type Impuesto as ImpuestoType,
  type Auditoria as AuditoriaType,
  type Usuario as UsuarioType,
  type Backup as BackupType,
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
// SECCIÓN: EMPRESA
// ============================================
function ConfiguracionEmpresa() {
  const [formData, setFormData] = useState<ConfigEmpresaType>({
    tipo_identificacion: "NIT",
    identificacion: "",
    dv: "",
    tipo_persona: "NATURAL",
    razon_social: "",
    regimen: "COMUN",
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
    cargarConfiguracion();
  }, []);

  const cargarConfiguracion = async () => {
    try {
      setCargando(true);
      const data = await configuracionEmpresaApi.obtener();
      setFormData(data);
    } catch (error) {
      console.error("Error al cargar configuración:", error);
      alert("Error al cargar la configuración de la empresa");
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
        }

        alert("Datos de empresa guardados exitosamente");
        await cargarConfiguracion();
      }
    } catch (error) {
      console.error("Error al guardar:", error);
      alert("Error al guardar los datos de la empresa");
    } finally {
      setGuardando(false);
    }
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setLogoFile(file);
    }
  };

  const handleCancel = () => {
    cargarConfiguracion();
    setLogoFile(null);
  };

  if (cargando) {
    return (
      <div className="p-6 flex items-center justify-center">
        <p className="text-gray-600">Cargando configuración...</p>
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
                  <option value="NATURAL">Persona natural</option>
                  <option value="JURIDICA">Persona jurídica</option>
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
                  <option value="COMUN">RÉGIMEN COMÚN</option>
                  <option value="SIMPLIFICADO">RÉGIMEN SIMPLIFICADO</option>
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
                <input
                  type="text"
                  placeholder="Departamento/Ciudad"
                  value={formData.ciudad}
                  onChange={(e) =>
                    setFormData({ ...formData, ciudad: e.target.value })
                  }
                  className="flex-1 px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <input
                  type="text"
                  placeholder="Municipio"
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
                  {formData.logo ? (
                    <img
                      src={formData.logo}
                      alt="Logo"
                      className="max-w-full max-h-full object-contain"
                    />
                  ) : (
                    <span className="text-gray-400 text-sm">Sin logo</span>
                  )}
                </div>
                <label className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded border border-gray-400 cursor-pointer">
                  Seleccionar
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoChange}
                    className="hidden"
                  />
                </label>
                {logoFile && (
                  <span className="text-sm text-gray-600 pt-2">
                    {logoFile.name}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Botones */}
          <div className="flex justify-start gap-3 pt-4 border-t border-gray-300">
            <button
              type="submit"
              disabled={guardando}
              className="px-6 py-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded flex items-center gap-2 font-semibold disabled:opacity-50"
            >
              <Save size={18} />
              {guardando ? "GUARDANDO..." : "GUARDAR"}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="px-6 py-2 bg-red-100 hover:bg-red-200 border border-red-400 rounded flex items-center gap-2"
            >
              <X size={18} />
              CANCELAR
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: USUARIOS
// ============================================
function ConfiguracionUsuarios() {
  const [usuarios, setUsuarios] = useState<UsuarioType[]>([]);
  const [cargando, setCargando] = useState(true);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [usuarioEditando, setUsuarioEditando] = useState<UsuarioType | null>(null);
  const [formData, setFormData] = useState<Partial<UsuarioType>>({
    username: "",
    email: "",
    first_name: "",
    last_name: "",
    tipo_usuario: "VENDEDOR",
    telefono: "",
    sede: "GAIRA",
    password: "",
  });

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

  const handleNuevoUsuario = () => {
    setUsuarioEditando(null);
    setFormData({
      username: "",
      email: "",
      first_name: "",
      last_name: "",
      tipo_usuario: "VENDEDOR",
      telefono: "",
      sede: "GAIRA",
      password: "",
    });
    setMostrarModal(true);
  };

  const handleEditarUsuario = (usuario: UsuarioType) => {
    setUsuarioEditando(usuario);
    setFormData({
      username: usuario.username,
      email: usuario.email,
      first_name: usuario.first_name,
      last_name: usuario.last_name,
      tipo_usuario: usuario.tipo_usuario,
      telefono: usuario.telefono,
      sede: usuario.sede,
    });
    setMostrarModal(true);
  };

  const handleGuardarUsuario = async () => {
    try {
      if (usuarioEditando) {
        // Actualizar
        await usuariosApi.actualizar(usuarioEditando.id!, formData);
        alert("Usuario actualizado exitosamente");
      } else {
        // Crear
        if (!formData.password) {
          alert("La contraseña es obligatoria para nuevos usuarios");
          return;
        }
        await usuariosApi.crear(formData);
        alert("Usuario creado exitosamente");
      }
      setMostrarModal(false);
      await cargarUsuarios();
    } catch (error) {
      console.error("Error al guardar usuario:", error);
      alert("Error al guardar el usuario");
    }
  };

  const handleDesactivar = async (id: number) => {
    if (confirm("¿Está seguro de desactivar este usuario?")) {
      try {
        await usuariosApi.desactivar(id);
        alert("Usuario desactivado exitosamente");
        await cargarUsuarios();
      } catch (error) {
        console.error("Error al desactivar usuario:", error);
        alert("Error al desactivar el usuario");
      }
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">
          Gestión de Usuarios
        </h1>
        <button
          onClick={handleNuevoUsuario}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
        >
          <Plus size={18} />
          Nuevo Usuario
        </button>
      </div>

      {cargando ? (
        <div className="text-center py-8">
          <p className="text-gray-600">Cargando usuarios...</p>
        </div>
      ) : (
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
              {usuarios.map((usuario) => (
                <tr key={usuario.id}>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.username}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.nombre_completo || "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.tipo_usuario}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {usuario.descuento_maximo}%
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
                      onClick={() => handleEditarUsuario(usuario)}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      <Edit2 size={16} className="inline" /> Editar
                    </button>
                    {usuario.is_active && (
                      <button
                        onClick={() => handleDesactivar(usuario.id!)}
                        className="text-red-600 hover:text-red-900"
                      >
                        <Trash2 size={16} className="inline" /> Desactivar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal de Edición/Creación */}
      {mostrarModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-bold mb-4">
              {usuarioEditando ? "Editar Usuario" : "Nuevo Usuario"}
            </h3>
            <div className="space-y-4">
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  disabled={!!usuarioEditando}
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
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
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="ADMIN">Administrador</option>
                  <option value="VENDEDOR">Vendedor</option>
                  <option value="MECANICO">Mecánico</option>
                  <option value="BODEGUERO">Bodeguero</option>
                </select>
              </div>
              {!usuarioEditando && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Contraseña
                  </label>
                  <input
                    type="password"
                    value={formData.password || ""}
                    onChange={(e) =>
                      setFormData({ ...formData, password: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
              )}
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setMostrarModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleGuardarUsuario}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================
// SECCIÓN: FACTURACIÓN (sin cambios)
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
// SECCIÓN: IMPUESTOS
// ============================================
function ConfiguracionImpuestos() {
  const [impuestos, setImpuestos] = useState<ImpuestoType[]>([]);
  const [nuevoValor, setNuevoValor] = useState("");
  const [cargando, setCargando] = useState(true);

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
      alert("Ingrese un valor para el impuesto");
      return;
    }

    try {
      const esNumero = !isNaN(Number(nuevoValor));
      await impuestosApi.crear({
        nombre: "IVA",
        valor: nuevoValor,
        porcentaje: esNumero ? Number(nuevoValor) : undefined,
        es_exento: nuevoValor.toUpperCase() === "E",
        is_active: true,
      });
      setNuevoValor("");
      await cargarImpuestos();
      alert("Impuesto agregado exitosamente");
    } catch (error) {
      console.error("Error al agregar impuesto:", error);
      alert("Error al agregar el impuesto");
    }
  };

  return (
    <div className="p-6">
      <div className="bg-white border border-gray-300 rounded-md shadow-sm p-6 max-w-md">
        <h2 className="text-lg font-bold mb-4">Impuestos</h2>

        {cargando ? (
          <p className="text-center text-gray-600">Cargando...</p>
        ) : (
          <>
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
                placeholder="Ej: 19 o E"
                className="w-24 px-3 py-2 border border-gray-300 rounded"
              />
              <button
                onClick={handleAgregarImpuesto}
                className="p-2 bg-blue-100 hover:bg-blue-200 border border-blue-400 rounded w-10 h-10 flex items-center justify-center"
                title="Guardar nuevo impuesto"
              >
                <Save size={18} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: AUDITORÍA
// ============================================
function ConfiguracionAuditoria() {
  const [auditorias, setAuditorias] = useState<AuditoriaType[]>([]);
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
      alert("Error al cargar el registro de auditoría");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="p-6">
      <div className="bg-white border border-gray-300 rounded-md shadow-sm">
        <div className="bg-blue-100 px-4 py-2 border-b border-gray-300">
          <h2 className="text-lg font-bold">Auditoría</h2>
        </div>

        {cargando ? (
          <div className="text-center py-8">
            <p className="text-gray-600">Cargando auditorías...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-100 border-b border-gray-300">
                  <th className="px-4 py-2 text-left text-sm font-semibold">
                    Fecha/Hora
                  </th>
                  <th className="px-4 py-2 text-left text-sm font-semibold">
                    Usuario
                  </th>
                  <th className="px-4 py-2 text-left text-sm font-semibold">
                    Acción
                  </th>
                  <th className="px-4 py-2 text-left text-sm font-semibold">
                    Notas
                  </th>
                </tr>
              </thead>
              <tbody>
                {auditorias.map((aud, index) => (
                  <tr
                    key={aud.id}
                    className={index % 2 === 0 ? "bg-blue-50" : "bg-white"}
                  >
                    <td className="px-4 py-2 text-sm border-r border-gray-200">
                      {new Date(aud.fecha_hora).toLocaleString("es-CO")}
                    </td>
                    <td className="px-4 py-2 text-sm border-r border-gray-200">
                      {aud.usuario_nombre}
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
        )}
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: CAMBIAR CONTRASEÑA
// ============================================
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

    setGuardando(true);
    try {
      await usuariosApi.cambiarPassword(formData);
      alert("Contraseña cambiada exitosamente");
      setFormData({ clave_actual: "", clave_nueva: "", confirmar_clave: "" });
    } catch (error: any) {
      console.error("Error al cambiar contraseña:", error);
      const mensaje =
        error.response?.data?.clave_actual?.[0] ||
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
              className="w-full px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
            >
              {guardando ? "Cambiando..." : "Cambiar Contraseña"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

// ============================================
// SECCIÓN: BACKUP/RESTAURAR
// ============================================
function BackupRestore() {
  const [backups, setBackups] = useState<BackupType[]>([]);
  const [cargando, setCargando] = useState(false);
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
    } finally {
      setCargando(false);
    }
  };

  const handleCrearBackup = async () => {
    setCreandoBackup(true);
    try {
      const result = await backupApi.crearBackup();
      alert(result.message);
      await cargarBackups();
    } catch (error) {
      console.error("Error al crear backup:", error);
      alert("Error al crear el backup");
    } finally {
      setCreandoBackup(false);
    }
  };

  const formatearTamaño = (bytes: number) => {
    if (bytes < 1024) return bytes + " bytes";
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
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium disabled:opacity-50"
          >
            {creandoBackup ? "Creando Backup..." : "Crear Backup Ahora"}
          </button>
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
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
                      Nombre
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
                      Fecha
                    </th>
                    <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">
                      Tamaño
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {backups.map((backup, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {backup.nombre}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {backup.fecha}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
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
