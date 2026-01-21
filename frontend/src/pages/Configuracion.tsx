import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CheckCircle2,
  Plus,
  Save,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
  X,
} from "lucide-react";
import { configuracionAPI } from "../api/configuracion";
import { tallerApi, type Mecanico } from "../api/taller";
import type {
  AuditoriaRegistro,
  ConfiguracionEmpresa,
  ConfiguracionFacturacion,
  Impuesto,
  UsuarioAdmin,
} from "../types";
import { useAuth } from "../contexts/AuthContext";
import {
  DEFAULT_MODULE_ACCESS,
  type ModuleAccess,
} from "../store/moduleAccess";

type ConfigTab =
  | "facturacion"
  | "empresa"
  | "impuestos"
  | "auditoria"
  | "usuarios"
  | "clave";

type PlantillaField =
  | "plantilla_factura_carta"
  | "plantilla_factura_tirilla"
  | "plantilla_remision_carta"
  | "plantilla_remision_tirilla"
  | "plantilla_nota_credito_carta"
  | "plantilla_nota_credito_tirilla";

const defaultEmpresa: ConfiguracionEmpresa = {
  id: 1,
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
  logo: null,
};

const defaultFacturacion: ConfiguracionFacturacion = {
  id: 1,
  prefijo_factura: "FAC",
  numero_factura: 100702,
  prefijo_remision: "",
  numero_remision: 154239,
  resolucion:
    "Resolución Facturación POS N°. 18764006081459 de 2020/10/22\nRango del 00001 al 50000.",
  notas_factura:
    "Para trámite de cambios y garantías, indispensable presentar la factura de venta. Tiene hasta 5 días para trámites. Los productos deben estar en perfecto estado y empaque original.",
  plantilla_factura_carta: "",
  plantilla_factura_tirilla: "",
  plantilla_remision_carta: "",
  plantilla_remision_tirilla: "",
  plantilla_nota_credito_carta: "",
  plantilla_nota_credito_tirilla: "",
};

const defaultImpuestos: Impuesto[] = [
  { id: -1, nombre: "IVA", valor: "0", porcentaje: "0", es_exento: true },
  { id: -2, nombre: "IVA", valor: "19", porcentaje: "19", es_exento: false },
  { id: -3, nombre: "IVA", valor: "E", porcentaje: null, es_exento: true },
];

export default function Configuracion() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const isAdmin = user?.role?.toUpperCase() === "ADMIN";
  const defaultTab: ConfigTab = isAdmin ? "facturacion" : "clave";
  const initialTab =
    (searchParams.get("tab") as ConfigTab) || defaultTab;

  const [activeTab, setActiveTab] = useState<ConfigTab>(initialTab);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa>(defaultEmpresa);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoRemoved, setLogoRemoved] = useState(false);
  const [facturacion, setFacturacion] =
    useState<ConfiguracionFacturacion>(defaultFacturacion);
  const [plantillaActiva, setPlantillaActiva] =
    useState<PlantillaField>("plantilla_factura_carta");
  const editorRef = useRef<HTMLDivElement | null>(null);
  const [impuestos, setImpuestos] = useState<Impuesto[]>(defaultImpuestos);
  const [auditoria, setAuditoria] = useState<AuditoriaRegistro[]>([]);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [mecanicosDisponibles, setMecanicosDisponibles] = useState<Mecanico[]>(
    []
  );
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [accessModalOpen, setAccessModalOpen] = useState(false);
  const [accessModalUser, setAccessModalUser] = useState<UsuarioAdmin | null>(
    null
  );
  const [userModalMode, setUserModalMode] = useState<"create" | "edit">(
    "create"
  );
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [origenUsuario, setOrigenUsuario] = useState<"manual" | "mecanico">(
    "manual"
  );
  const [mecanicoSeleccionado, setMecanicoSeleccionado] = useState<
    number | ""
  >("");
  const [nuevoUsuario, setNuevoUsuario] = useState({
    username: "",
    email: "",
    first_name: "",
    last_name: "",
    telefono: "",
    tipo_usuario: "VENDEDOR" as UsuarioAdmin["tipo_usuario"],
    is_active: true,
    password: "",
  });
  const [nuevoImpuesto, setNuevoImpuesto] = useState<Partial<Impuesto>>({
    nombre: "IVA",
    valor: "",
    porcentaje: "",
  });

  const [mensajeEmpresa, setMensajeEmpresa] = useState("");
  const [mensajeClave, setMensajeClave] = useState("");
  const [mensajeFacturacion, setMensajeFacturacion] = useState("");
  const [mensajeImpuesto, setMensajeImpuesto] = useState("");
  const [mensajeUsuario, setMensajeUsuario] = useState("");
  const [mensajeNuevoUsuario, setMensajeNuevoUsuario] = useState("");
  const [mensajeAccesos, setMensajeAccesos] = useState("");

  const [claveActual, setClaveActual] = useState("");
  const [nuevaClave, setNuevaClave] = useState("");
  const [confirmarClave, setConfirmarClave] = useState("");

  const [accesosModulos, setAccesosModulos] = useState<ModuleAccess>(
    DEFAULT_MODULE_ACCESS
  );
  const [accesosModulosId, setAccesosModulosId] = useState<number | null>(null);

  const tabs = useMemo(() => {
    if (!isAdmin) {
      return [
        { id: "clave", label: "Cambiar clave", icon: <UserCog size={18} /> },
      ];
    }

    return [
      {
        id: "facturacion",
        label: "Facturación",
        icon: <ShieldCheck size={18} />,
      },
      { id: "empresa", label: "Empresa", icon: <UserCog size={18} /> },
      { id: "usuarios", label: "Usuarios", icon: <Users size={18} /> },
      { id: "impuestos", label: "Impuestos", icon: <Plus size={18} /> },
      { id: "auditoria", label: "Auditoría", icon: <Users size={18} /> },
      { id: "clave", label: "Cambiar clave", icon: <UserCog size={18} /> },
    ];
  }, [isAdmin]);

  const availableTabs = useMemo(
    () => tabs.map((tab) => tab.id as ConfigTab),
    [tabs]
  );

  const plantillaOptions = useMemo(
    () => [
      {
        id: "plantilla_factura_carta",
        label: "Factura de venta · Carta",
      },
      {
        id: "plantilla_factura_tirilla",
        label: "Factura de venta · Tirilla",
      },
      {
        id: "plantilla_remision_carta",
        label: "Remisión · Carta",
      },
      {
        id: "plantilla_remision_tirilla",
        label: "Remisión · Tirilla",
      },
      {
        id: "plantilla_nota_credito_carta",
        label: "Nota crédito · Carta",
      },
      {
        id: "plantilla_nota_credito_tirilla",
        label: "Nota crédito · Tirilla",
      },
    ],
    []
  );

  const moduleOptions = useMemo<
    Array<{ key: keyof ModuleAccess; label: string; description: string }>
  >(
    () => [
      {
        key: "configuracion",
        label: "Configuración",
        description: "Permite acceder a la información y ajustes del sistema.",
      },
      {
        key: "registrar",
        label: "Registrar",
        description: "Habilita el registro general de operaciones.",
      },
      {
        key: "listados",
        label: "Listados",
        description: "Acceso a clientes, proveedores, empleados y categorías.",
      },
      {
        key: "articulos",
        label: "Artículos",
        description: "Inventario, stock y bajas de mercancía.",
      },
      {
        key: "taller",
        label: "Taller",
        description: "Operaciones y registro de motos del taller.",
      },
      {
        key: "facturacion",
        label: "Facturación",
        description: "Venta rápida, cuentas y listados de facturas.",
      },
      {
        key: "reportes",
        label: "Reportes",
        description: "Visualización de reportes diarios y mensuales.",
      },
    ],
    []
  );

  useEffect(() => {
    const tabParam = searchParams.get("tab") as ConfigTab | null;
    if (tabParam && availableTabs.includes(tabParam)) {
      if (tabParam !== activeTab) {
        setActiveTab(tabParam);
      }
      return;
    }
    if (!availableTabs.includes(activeTab)) {
      const fallback = availableTabs[0] ?? defaultTab;
      setActiveTab(fallback);
      setSearchParams({ tab: fallback });
    }
  }, [activeTab, availableTabs, defaultTab, searchParams, setSearchParams]);

  useEffect(() => {
    const cargarDatos = async () => {
      try {
        const data = await configuracionAPI.obtenerEmpresa();
        if (data) {
          setEmpresa(data);
          setLogoPreview(data.logo);
          if (data.logo) {
            localStorage.setItem("empresa_logo", data.logo);
          } else {
            localStorage.removeItem("empresa_logo");
          }
        }
      } catch (error) {
        console.error("Error cargando empresa:", error);
      }

      try {
        const data = await configuracionAPI.obtenerFacturacion();
        if (data) {
          setFacturacion(data);
        }
      } catch (error) {
        console.error("Error cargando facturación:", error);
      }

      if (!isAdmin) {
        return;
      }

      try {
        const data = await configuracionAPI.obtenerImpuestos();
        if (data?.length) {
          setImpuestos(data);
        }
      } catch (error) {
        console.error("Error cargando impuestos:", error);
      }

      try {
        const data = await configuracionAPI.obtenerAuditoria();
        if (data?.length) {
          setAuditoria(data);
        }
      } catch (error) {
        console.error("Error cargando auditoría:", error);
      }
    };

    cargarDatos();
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }

    const cargarUsuarios = async () => {
      try {
        const data = await configuracionAPI.obtenerUsuarios();
        setUsuarios(data);
      } catch (error) {
        console.error("Error cargando usuarios:", error);
      }
    };

    cargarUsuarios();
  }, [isAdmin]);

  useEffect(() => {
    if (!user?.id || isAdmin) {
      return;
    }

    const cargarPerfil = async () => {
      try {
        const data = await configuracionAPI.obtenerUsuarioActual();
        setPerfil(data);
      } catch (error) {
        console.error("Error cargando perfil:", error);
      }
    };

    cargarPerfil();
  }, [isAdmin, user?.id]);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }

    const cargarAccesos = async () => {
      try {
        const data = await configuracionAPI.obtenerAccesosModulos();
        setAccesosModulos(data.access);
        setAccesosModulosId(data.id);
      } catch (error) {
        console.error("Error cargando accesos de módulos:", error);
      }
    };

    cargarAccesos();
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }

    const cargarMecanicos = async () => {
      try {
      const data = await tallerApi.getMecanicos({ is_active: true });
        const parsed = Array.isArray(data) ? data : data.results ?? [];
        setMecanicosDisponibles(parsed);
      } catch (error) {
        console.error("Error cargando mecánicos:", error);
        setMecanicosDisponibles([]);
      }
    };

    cargarMecanicos();
  }, [isAdmin]);

  useEffect(() => {
    if (!logoFile) {
      return;
    }
    const objectUrl = URL.createObjectURL(logoFile);
    setLogoPreview(objectUrl);
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [logoFile]);

  useEffect(() => {
    if (!editorRef.current) {
      return;
    }
    editorRef.current.innerHTML = facturacion[plantillaActiva] || "";
  }, [facturacion, plantillaActiva]);

  const onTabChange = (tabId: ConfigTab) => {
    setActiveTab(tabId);
    setSearchParams({ tab: tabId });
  };

  const handleGuardarEmpresa = async () => {
    try {
      const data = await configuracionAPI.actualizarEmpresa(
        empresa.id,
        empresa,
        { logoFile, removeLogo: logoRemoved }
      );
      setEmpresa(data);
      setLogoFile(null);
      setLogoRemoved(false);
      setLogoPreview(data.logo);
      if (data.logo) {
        localStorage.setItem("empresa_logo", data.logo);
      } else {
        localStorage.removeItem("empresa_logo");
      }
      setMensajeEmpresa("Los datos han sido actualizados correctamente.");
    } catch (error) {
      console.error("Error actualizando empresa:", error);
      setMensajeEmpresa(
        "No se pudo actualizar la información. Intenta nuevamente."
      );
    }
  };

  const handleGuardarFacturacion = async () => {
    try {
      const data = await configuracionAPI.actualizarFacturacion(
        facturacion.id,
        facturacion
      );
      setFacturacion(data);
      setMensajeFacturacion("Configuración de facturación actualizada.");
    } catch (error) {
      console.error("Error actualizando facturación:", error);
      setMensajeFacturacion("No se pudo actualizar la facturación.");
    }
  };

  const handleAgregarImpuesto = async () => {
    if (!nuevoImpuesto.nombre || !nuevoImpuesto.valor) {
      setMensajeImpuesto("Completa el nombre y el valor del impuesto.");
      return;
    }

    try {
      const nuevo = await configuracionAPI.crearImpuesto({
        nombre: nuevoImpuesto.nombre,
        valor: nuevoImpuesto.valor,
        porcentaje: nuevoImpuesto.porcentaje || null,
        es_exento: nuevoImpuesto.valor === "E",
      });
      setImpuestos((prev) => [...prev, nuevo]);
      setNuevoImpuesto({ nombre: "IVA", valor: "", porcentaje: "" });
      setMensajeImpuesto("Impuesto agregado correctamente.");
    } catch (error) {
      console.error("Error agregando impuesto:", error);
      setMensajeImpuesto("No se pudo agregar el impuesto.");
    }
  };

  const handleEliminarImpuesto = async (impuesto: Impuesto) => {
    try {
      if (impuesto.id > 0) {
        await configuracionAPI.eliminarImpuesto(impuesto.id);
      }
      setImpuestos((prev) => prev.filter((item) => item.id !== impuesto.id));
    } catch (error) {
      console.error("Error eliminando impuesto:", error);
      setMensajeImpuesto("No se pudo quitar el impuesto.");
    }
  };

  const handleActualizarUsuario = async (usuario: UsuarioAdmin) => {
    try {
      const data = await configuracionAPI.actualizarUsuario(usuario.id, {
        tipo_usuario: usuario.tipo_usuario,
        is_active: usuario.is_active,
      });
      setUsuarios((prev) =>
        prev.map((item) => (item.id === data.id ? data : item))
      );
      setMensajeUsuario("Cambios guardados para el usuario.");
    } catch (error) {
      console.error("Error actualizando usuario:", error);
      setMensajeUsuario("No se pudo actualizar el usuario.");
    }
  };

  const handleGuardarAccesos = async () => {
    if (!accesosModulosId) {
      setMensajeAccesos("No se encontró la configuración de módulos.");
      return;
    }

    try {
      const data = await configuracionAPI.actualizarAccesosModulos(
        accesosModulosId,
        accesosModulos
      );
      setAccesosModulos(data.access);
      setMensajeAccesos("Accesos de módulos actualizados.");
      window.dispatchEvent(new Event("module-access-updated"));
    } catch (error) {
      console.error("Error actualizando accesos de módulos:", error);
      setMensajeAccesos("No se pudieron actualizar los accesos.");
    }
  };

  const resetNuevoUsuario = () => {
    setNuevoUsuario({
      username: "",
      email: "",
      first_name: "",
      last_name: "",
      telefono: "",
      tipo_usuario: "VENDEDOR",
      is_active: true,
      password: "",
    });
    setMecanicoSeleccionado("");
    setOrigenUsuario("manual");
    setEditingUserId(null);
  };

  const openCreateUserModal = () => {
    setUserModalMode("create");
    resetNuevoUsuario();
    setMensajeNuevoUsuario("");
    setUserModalOpen(true);
  };

  const openEditUserModal = (usuario: UsuarioAdmin) => {
    setUserModalMode("edit");
    setEditingUserId(usuario.id);
    setNuevoUsuario({
      username: usuario.username,
      email: usuario.email || "",
      first_name: usuario.first_name || "",
      last_name: usuario.last_name || "",
      telefono: usuario.telefono || "",
      tipo_usuario: usuario.tipo_usuario,
      is_active: usuario.is_active,
      password: "",
    });
    setMensajeNuevoUsuario("");
    setUserModalOpen(true);
  };

  const openAccessModal = (usuario: UsuarioAdmin) => {
    setAccessModalUser(usuario);
    setMensajeAccesos("");
    setAccessModalOpen(true);
  };

  const closeAccessModal = () => {
    setAccessModalOpen(false);
    setAccessModalUser(null);
    setMensajeAccesos("");
  };

  const handleGuardarUsuarioModal = async () => {
    if (!nuevoUsuario.username || !nuevoUsuario.tipo_usuario) {
      setMensajeNuevoUsuario("Completa el usuario y el rol para continuar.");
      return;
    }

    if (userModalMode === "create" && !nuevoUsuario.password) {
      setMensajeNuevoUsuario("Debes asignar una contraseña al usuario.");
      return;
    }

    try {
      if (userModalMode === "create") {
        const payload = {
          username: nuevoUsuario.username,
          email: nuevoUsuario.email || "",
          first_name: nuevoUsuario.first_name || "",
          last_name: nuevoUsuario.last_name || "",
          telefono: nuevoUsuario.telefono || "",
          tipo_usuario: nuevoUsuario.tipo_usuario,
          is_active: nuevoUsuario.is_active,
          password: nuevoUsuario.password,
        };
        const data = await configuracionAPI.crearUsuario(payload);
        setUsuarios((prev) => [data, ...prev]);
        setMensajeNuevoUsuario("Usuario creado correctamente.");
      } else {
        if (!editingUserId) {
          setMensajeNuevoUsuario(
            "No se encontró el usuario a editar. Refresca la lista."
          );
          return;
        }
        const payload: Partial<UsuarioAdmin> & { password?: string } = {
          username: nuevoUsuario.username,
          email: nuevoUsuario.email || "",
          first_name: nuevoUsuario.first_name || "",
          last_name: nuevoUsuario.last_name || "",
          telefono: nuevoUsuario.telefono || "",
          tipo_usuario: nuevoUsuario.tipo_usuario,
          is_active: nuevoUsuario.is_active,
        };
        if (nuevoUsuario.password) {
          payload.password = nuevoUsuario.password;
        }
        const data = await configuracionAPI.actualizarUsuario(editingUserId, payload);
        setUsuarios((prev) =>
          prev.map((item) => (item.id === data.id ? data : item))
        );
        setMensajeNuevoUsuario("Usuario actualizado correctamente.");
      }
      setUserModalOpen(false);
      resetNuevoUsuario();
    } catch (error) {
      console.error("Error guardando usuario:", error);
      setMensajeNuevoUsuario("No se pudo guardar el usuario.");
    }
  };

  useEffect(() => {
    if (origenUsuario !== "mecanico" || userModalMode !== "create") {
      return;
    }
    const mecanico = mecanicosDisponibles.find(
      (item) => item.id === mecanicoSeleccionado
    );
    if (!mecanico) {
      return;
    }
    const partesNombre = mecanico.nombre.split(" ").filter(Boolean);
    const firstName = partesNombre[0] ?? "";
    const lastName = partesNombre.slice(1).join(" ");
    const usernameBase =
      mecanico.email?.split("@")[0] ?? mecanico.nombre.toLowerCase();
    const username = usernameBase
      .trim()
      .replace(/\s+/g, ".")
      .replace(/[^a-z0-9._-]/gi, "");

    setNuevoUsuario((prev) => ({
      ...prev,
      username: prev.username || username,
      email: mecanico.email ?? prev.email,
      telefono: mecanico.telefono ?? prev.telefono,
      first_name: prev.first_name || firstName,
      last_name: prev.last_name || lastName,
      tipo_usuario: "MECANICO",
    }));
  }, [
    mecanicoSeleccionado,
    mecanicosDisponibles,
    origenUsuario,
    userModalMode,
  ]);

  const handleCambiarClave = async () => {
    if (!user?.id) {
      setMensajeClave("No se pudo identificar el usuario actual.");
      return;
    }

    if (!nuevaClave || nuevaClave !== confirmarClave) {
      setMensajeClave("La nueva clave y la confirmación no coinciden.");
      return;
    }

    try {
      await configuracionAPI.cambiarClave(user.id, nuevaClave);
      setClaveActual("");
      setNuevaClave("");
      setConfirmarClave("");
      setMensajeClave("La clave ha sido actualizada correctamente.");
    } catch (error) {
      console.error("Error cambiando clave:", error);
      setMensajeClave("No se pudo actualizar la clave.");
    }
  };

  const actualizarPlantilla = (value: string) => {
    setFacturacion((prev) => ({
      ...prev,
      [plantillaActiva]: value,
    }));
  };

  const aplicarFormato = (comando: string, valor?: string) => {
    if (!editorRef.current) {
      return;
    }
    editorRef.current.focus();
    document.execCommand(comando, false, valor);
    actualizarPlantilla(editorRef.current.innerHTML);
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-900">
          Módulo de configuración
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Gestiona facturación, impuestos, datos de empresa, auditoría y
          usuarios desde un solo lugar.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id as ConfigTab)}
              className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition ${
                activeTab === tab.id
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-200 text-slate-600 hover:border-blue-300 hover:text-blue-600"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "facturacion" && (
        <section className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="rounded-2xl bg-white p-6 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">
                    Numeración para facturas de venta
                  </h3>
                  <p className="text-sm text-slate-500">
                    Esta sección se sincronizará con la cantidad de facturas
                    del sistema.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleGuardarFacturacion}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700"
                >
                  <Save size={16} /> Guardar
                </button>
              </div>

              {mensajeFacturacion && (
                <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  {mensajeFacturacion}
                </div>
              )}

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <label className="space-y-2 text-sm font-medium text-slate-700">
                  Prefijo
                  <input
                    value={facturacion.prefijo_factura}
                    onChange={(event) =>
                      setFacturacion((prev) => ({
                        ...prev,
                        prefijo_factura: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-700">
                  Número
                  <input
                    type="number"
                    value={facturacion.numero_factura}
                    onChange={(event) =>
                      setFacturacion((prev) => ({
                        ...prev,
                        numero_factura: Number(event.target.value),
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-700">
                  Prefijo remisión
                  <input
                    value={facturacion.prefijo_remision}
                    onChange={(event) =>
                      setFacturacion((prev) => ({
                        ...prev,
                        prefijo_remision: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-700">
                  Número remisión
                  <input
                    type="number"
                    value={facturacion.numero_remision}
                    onChange={(event) =>
                      setFacturacion((prev) => ({
                        ...prev,
                        numero_remision: Number(event.target.value),
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
              </div>

              <div className="mt-6 grid gap-4">
                <label className="space-y-2 text-sm font-medium text-slate-700">
                  Resolución
                  <textarea
                    value={facturacion.resolucion}
                    onChange={(event) =>
                      setFacturacion((prev) => ({
                        ...prev,
                        resolucion: event.target.value,
                      }))
                    }
                    rows={4}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-sm font-medium text-slate-700">
                  Notas de la factura de venta
                  <textarea
                    value={facturacion.notas_factura}
                    onChange={(event) =>
                      setFacturacion((prev) => ({
                        ...prev,
                        notas_factura: event.target.value,
                      }))
                    }
                    rows={3}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
              </div>
            </div>

          </div>

          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h4 className="text-sm font-semibold text-slate-500">
              Estado actual
            </h4>
            <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50 p-4">
              <p className="text-3xl font-semibold text-slate-900">0</p>
              <p className="text-sm text-slate-500">Facturas registradas</p>
            </div>
            <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-700">
              Este panel tomará los datos reales cuando el backend entregue el
              conteo de facturas.
            </div>
          </div>
        </section>
      )}

      {activeTab === "impuestos" && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                Impuestos
              </h3>
              <p className="text-sm text-slate-500">
                Los impuestos principales permanecen fijos, pero puedes agregar
                o quitar adicionales.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setImpuestos(defaultImpuestos)}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:border-red-200 hover:text-red-600"
              title="Restablecer a impuestos base"
            >
              <X size={16} /> Restablecer
            </button>
          </div>

          {mensajeImpuesto && (
            <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {mensajeImpuesto}
            </div>
          )}

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {impuestos.map((impuesto) => (
              <div
                key={impuesto.id}
                className="rounded-xl border border-slate-100 bg-slate-50 p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      {impuesto.nombre}
                    </p>
                    <p className="text-xs text-slate-500">
                      Valor: {impuesto.valor}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleEliminarImpuesto(impuesto)}
                    className="rounded-full border border-transparent p-1 text-slate-400 hover:border-red-200 hover:text-red-600"
                    title="Quitar impuesto"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  {impuesto.es_exento
                    ? "Exento"
                    : `Porcentaje: ${impuesto.porcentaje ?? "N/A"}%`}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-xl border border-dashed border-slate-200 p-4">
            <h4 className="text-sm font-semibold text-slate-700">
              Agregar impuesto
            </h4>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <label className="space-y-2 text-sm font-medium text-slate-700">
                Nombre
                <input
                  value={nuevoImpuesto.nombre}
                  onChange={(event) =>
                    setNuevoImpuesto((prev) => ({
                      ...prev,
                      nombre: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-700">
                Valor
                <input
                  value={nuevoImpuesto.valor}
                  onChange={(event) =>
                    setNuevoImpuesto((prev) => ({
                      ...prev,
                      valor: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-700">
                Porcentaje
                <input
                  value={nuevoImpuesto.porcentaje ?? ""}
                  onChange={(event) =>
                    setNuevoImpuesto((prev) => ({
                      ...prev,
                      porcentaje: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
            </div>
            <button
              type="button"
              onClick={handleAgregarImpuesto}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700"
            >
              <Plus size={16} /> Agregar impuesto
            </button>
          </div>
        </section>
      )}

      {activeTab === "empresa" && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                Actualiza los datos generales de tu empresa
              </h3>
              <p className="text-sm text-slate-500">
                Puedes editar la información directamente y guardar los cambios.
              </p>
            </div>
            <button
              type="button"
              onClick={handleGuardarEmpresa}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700"
            >
              <Save size={16} /> Guardar
            </button>
          </div>

          {mensajeEmpresa && (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              <CheckCircle2 size={16} />
              {mensajeEmpresa}
            </div>
          )}

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="space-y-2 text-sm font-medium text-slate-700 md:col-span-2">
              Logo
              <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 p-4">
                <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-slate-100 text-base font-semibold text-slate-500">
                  {logoPreview ? (
                    <img
                      src={logoPreview}
                      alt="Logo actual"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    "LA"
                  )}
                </div>
                <div className="flex flex-1 flex-col gap-2">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                      const file = event.target.files?.[0] || null;
                      setLogoFile(file);
                      setLogoRemoved(false);
                      if (!file) {
                        setLogoPreview(empresa.logo);
                      }
                    }}
                    className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-blue-600 hover:file:bg-blue-100"
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setLogoFile(null);
                        setLogoRemoved(true);
                        setLogoPreview(null);
                        setEmpresa((prev) => ({ ...prev, logo: null }));
                      }}
                      className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 hover:border-red-200 hover:text-red-600"
                    >
                      Quitar logo
                    </button>
                    <p className="text-xs text-slate-500">
                      Recomendado: imagen cuadrada en PNG o JPG.
                    </p>
                  </div>
                </div>
              </div>
            </div>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Tipo de identificación
              <select
                value={empresa.tipo_identificacion}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    tipo_identificacion: event.target
                      .value as ConfiguracionEmpresa["tipo_identificacion"],
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <option value="NIT">
                  NÚMERO DE IDENTIFICACIÓN TRIBUTARIA (NIT)
                </option>
                <option value="CC">CÉDULA DE CIUDADANÍA</option>
                <option value="CE">CÉDULA DE EXTRANJERÍA</option>
              </select>
            </label>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="space-y-2 text-sm font-medium text-slate-700 md:col-span-2">
                Identificación
                <input
                  value={empresa.identificacion}
                  onChange={(event) =>
                    setEmpresa((prev) => ({
                      ...prev,
                      identificacion: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-700">
                DV
                <input
                  value={empresa.dv}
                  onChange={(event) =>
                    setEmpresa((prev) => ({ ...prev, dv: event.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
            </div>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Tipo de persona
              <select
                value={empresa.tipo_persona}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    tipo_persona: event.target
                      .value as ConfiguracionEmpresa["tipo_persona"],
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <option value="Persona natural">Persona natural</option>
                <option value="Persona jurídica">Persona jurídica</option>
              </select>
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Razón social
              <input
                value={empresa.razon_social}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    razon_social: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Régimen
              <select
                value={empresa.regimen}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    regimen: event.target
                      .value as ConfiguracionEmpresa["regimen"],
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <option value="RÉGIMEN COMÚN">RÉGIMEN COMÚN</option>
                <option value="RÉGIMEN SIMPLIFICADO">
                  RÉGIMEN SIMPLIFICADO
                </option>
              </select>
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Dirección
              <input
                value={empresa.direccion}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    direccion: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-2 text-sm font-medium text-slate-700">
                Ciudad
                <input
                  value={empresa.ciudad}
                  onChange={(event) =>
                    setEmpresa((prev) => ({
                      ...prev,
                      ciudad: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-700">
                Municipio
                <input
                  value={empresa.municipio}
                  onChange={(event) =>
                    setEmpresa((prev) => ({
                      ...prev,
                      municipio: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                />
              </label>
            </div>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Teléfono
              <input
                value={empresa.telefono}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    telefono: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Sitio web
              <input
                value={empresa.sitio_web}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    sitio_web: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Correo
              <input
                value={empresa.correo}
                onChange={(event) =>
                  setEmpresa((prev) => ({
                    ...prev,
                    correo: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
          </div>
        </section>
      )}

      {activeTab === "auditoria" && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Auditoría</h3>
          <p className="text-sm text-slate-500">
            Cada movimiento entre módulos y cambios de usuarios se registra
            automáticamente.
          </p>

          <div className="mt-6 overflow-hidden rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Fecha</th>
                  <th className="px-4 py-3">Usuario</th>
                  <th className="px-4 py-3">Acción</th>
                  <th className="px-4 py-3">Notas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {auditoria.length === 0 ? (
                  <tr>
                    <td className="px-4 py-4 text-slate-500" colSpan={4}>
                      Aún no hay movimientos registrados.
                    </td>
                  </tr>
                ) : (
                  auditoria.slice(0, 10).map((registro) => (
                    <tr key={registro.id} className="text-slate-700">
                      <td className="px-4 py-3">
                        {new Date(registro.fecha_hora).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">{registro.usuario_nombre}</td>
                      <td className="px-4 py-3">{registro.accion}</td>
                      <td className="px-4 py-3">{registro.notas}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activeTab === "usuarios" && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">Usuarios</h3>
          <p className="text-sm text-slate-500">
            Solo los administradores pueden administrar accesos y permisos de
            los usuarios.
          </p>

          {!isAdmin ? (
            <div className="mt-6 rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              Tu perfil no tiene permisos para administrar usuarios.
            </div>
          ) : (
            <>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div>
                  <h4 className="text-sm font-semibold text-slate-700">
                    Gestiona usuarios
                  </h4>
                  <p className="text-xs text-slate-500">
                    Crea usuarios desde cero o usando mecánicos existentes.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={openCreateUserModal}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-blue-700"
                >
                  <Plus size={14} /> Crear usuario
                </button>
              </div>

              {mensajeUsuario && (
                <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  {mensajeUsuario}
                </div>
              )}
              <div className="mt-6 overflow-hidden rounded-xl border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Usuario</th>
                      <th className="px-4 py-3">Rol</th>
                      <th className="px-4 py-3">Estado</th>
                      <th className="px-4 py-3">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {usuarios.map((usuario) => (
                      <tr key={usuario.id} className="text-slate-700">
                        <td className="px-4 py-3">
                          <p className="font-medium">{usuario.username}</p>
                          <p className="text-xs text-slate-500">
                            {usuario.email}
                          </p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600">
                            {usuario.tipo_usuario === "ADMIN"
                              ? "Administrador"
                              : usuario.tipo_usuario === "VENDEDOR"
                              ? "Vendedor"
                              : usuario.tipo_usuario === "MECANICO"
                              ? "Mecánico"
                              : "Bodeguero"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <label className="inline-flex items-center gap-2 text-xs text-slate-600">
                            <input
                              type="checkbox"
                              checked={usuario.is_active}
                              onChange={(event) =>
                                setUsuarios((prev) =>
                                  prev.map((item) =>
                                    item.id === usuario.id
                                      ? {
                                          ...item,
                                          is_active: event.target.checked,
                                        }
                                      : item
                                  )
                                )
                              }
                            />
                            {usuario.is_active ? "Activo" : "Inactivo"}
                          </label>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => handleActualizarUsuario(usuario)}
                            className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-800"
                          >
                            Guardar
                          </button>
                          <button
                            type="button"
                            onClick={() => openAccessModal(usuario)}
                            className="ml-2 rounded-lg border border-blue-200 px-3 py-1 text-xs font-medium text-blue-600 hover:border-blue-400"
                          >
                            Accesos
                          </button>
                          <button
                            type="button"
                            onClick={() => openEditUserModal(usuario)}
                            className="ml-2 rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:border-blue-200 hover:text-blue-600"
                          >
                            Editar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {activeTab === "clave" && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">
            Cambiar clave
          </h3>
          <p className="text-sm text-slate-500">
            Actualiza tu clave de acceso. Esta acción quedará registrada en
            auditoría.
          </p>

          {mensajeClave && (
            <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {mensajeClave}
            </div>
          )}

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Clave actual
              <input
                type="password"
                value={claveActual}
                onChange={(event) => setClaveActual(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Nueva clave
              <input
                type="password"
                value={nuevaClave}
                onChange={(event) => setNuevaClave(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
            <label className="space-y-2 text-sm font-medium text-slate-700">
              Confirmar nueva clave
              <input
                type="password"
                value={confirmarClave}
                onChange={(event) => setConfirmarClave(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={handleCambiarClave}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700"
          >
            <Save size={16} /> Guardar nueva clave
          </button>
        </section>
      )}

      {userModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
          <div className="w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-blue-500">
                  {userModalMode === "create"
                    ? "Nuevo usuario"
                    : "Editar usuario"}
                </p>
                <h2 className="text-lg font-semibold text-slate-900">
                  {userModalMode === "create"
                    ? "Registrar usuario"
                    : "Actualizar usuario"}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setUserModalOpen(false);
                  resetNuevoUsuario();
                  setMensajeNuevoUsuario("");
                }}
                className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-6 px-6 py-4">
              {mensajeNuevoUsuario && (
                <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  {mensajeNuevoUsuario}
                </div>
              )}

              {userModalMode === "create" && (
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-xs font-medium text-slate-700">
                    Origen
                    <select
                      value={origenUsuario}
                      onChange={(event) => {
                        const value = event.target.value as
                          | "manual"
                          | "mecanico";
                        setOrigenUsuario(value);
                        setMecanicoSeleccionado("");
                        setNuevoUsuario((prev) => ({
                          ...prev,
                          username: "",
                          email: "",
                          first_name: "",
                          last_name: "",
                          telefono: "",
                        }));
                      }}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    >
                      <option value="manual">Manual</option>
                      <option value="mecanico">Mecánico existente</option>
                    </select>
                  </label>

                  {origenUsuario === "mecanico" && (
                    <label className="space-y-2 text-xs font-medium text-slate-700">
                      Mecánico
                      <select
                        value={mecanicoSeleccionado}
                        onChange={(event) =>
                          setMecanicoSeleccionado(
                            event.target.value
                              ? Number(event.target.value)
                              : ""
                          )
                        }
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      >
                        <option value="">Selecciona un mecánico</option>
                        {mecanicosDisponibles.map((mecanico) => (
                          <option key={mecanico.id} value={mecanico.id}>
                            {mecanico.nombre}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>
              )}

              <div className="grid gap-4 md:grid-cols-3">
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Usuario
                  <input
                    value={nuevoUsuario.username}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        username: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Correo
                  <input
                    value={nuevoUsuario.email}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        email: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Teléfono
                  <input
                    value={nuevoUsuario.telefono}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        telefono: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Nombre
                  <input
                    value={nuevoUsuario.first_name}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        first_name: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Apellido
                  <input
                    value={nuevoUsuario.last_name}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        last_name: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                </label>
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Rol
                  <select
                    value={nuevoUsuario.tipo_usuario}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        tipo_usuario: event.target
                          .value as UsuarioAdmin["tipo_usuario"],
                      }))
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  >
                    <option value="ADMIN">Administrador</option>
                    <option value="VENDEDOR">Vendedor</option>
                    <option value="MECANICO">Mecánico</option>
                    <option value="BODEGUERO">Bodeguero</option>
                  </select>
                </label>
                <label className="space-y-2 text-xs font-medium text-slate-700">
                  Contraseña
                  <input
                    type="password"
                    value={nuevoUsuario.password}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        password: event.target.value,
                      }))
                    }
                    placeholder={
                      userModalMode === "edit"
                        ? "Dejar en blanco para mantener"
                        : ""
                    }
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  />
                  {userModalMode === "edit" && (
                    <p className="text-[11px] font-normal text-slate-500">
                      Por seguridad no se muestra la contraseña actual. Ingresa
                      una nueva si deseas actualizarla.
                    </p>
                  )}
                </label>
                <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={nuevoUsuario.is_active}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        is_active: event.target.checked,
                      }))
                    }
                  />
                  Usuario activo
                </label>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setUserModalOpen(false);
                    resetNuevoUsuario();
                    setMensajeNuevoUsuario("");
                  }}
                  className="rounded-full border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:border-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleGuardarUsuarioModal}
                  className="rounded-full bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
                >
                  {userModalMode === "create" ? "Crear usuario" : "Guardar"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {accessModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
          <div className="w-full max-w-3xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-blue-500">
                  Accesos por módulos
                </p>
                <h2 className="text-lg font-semibold text-slate-900">
                  {accessModalUser
                    ? `Accesos de ${accessModalUser.username}`
                    : "Configurar accesos"}
                </h2>
              </div>
              <button
                type="button"
                onClick={closeAccessModal}
                className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100"
              >
                <X size={18} />
              </button>
            </div>
            <div className="space-y-6 px-6 py-4">
              <p className="text-sm text-slate-500">
                Activa o desactiva los módulos disponibles para los perfiles
                operativos.
              </p>

              {mensajeAccesos && (
                <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  {mensajeAccesos}
                </div>
              )}

              <div className="grid gap-4 md:grid-cols-2">
                {moduleOptions.map((modulo) => (
                  <label
                    key={modulo.key}
                    className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        {modulo.label}
                      </p>
                      <p className="text-xs text-slate-500">
                        {modulo.description}
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={accesosModulos[modulo.key]}
                      onChange={(event) =>
                        setAccesosModulos((prev) => ({
                          ...prev,
                          [modulo.key]: event.target.checked,
                        }))
                      }
                      className="h-5 w-5 accent-blue-600"
                    />
                  </label>
                ))}
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
                Estado por defecto:{" "}
                {Object.keys(DEFAULT_MODULE_ACCESS).length} módulos habilitados.
              </div>

              <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={closeAccessModal}
                  className="rounded-full border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:border-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleGuardarAccesos}
                  className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
                >
                  <Save size={16} /> Guardar accesos
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
