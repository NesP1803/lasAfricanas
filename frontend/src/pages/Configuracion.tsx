import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
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
import { usuariosApi } from "../api/usuarios";
import ConfirmModal from "../components/ConfirmModal";
import Pagination from "../components/Pagination";
import type {
  AuditoriaRegistro,
  AuditoriaRetention,
  ConfiguracionEmpresa,
  ConfiguracionFacturacion,
  Impuesto,
  UsuarioAdmin,
} from "../types";
import { useAuth } from "../contexts/AuthContext";
import { useNotification } from "../contexts/NotificationContext";
import {
  MODULE_DEFINITIONS,
  createEmptyModuleAccess,
  isSectionEnabled,
  normalizeModuleAccess,
  type ModuleAccessState,
} from "../store/moduleAccess";

type ConfigTab =
  | "facturacion"
  | "empresa"
  | "impuestos"
  | "auditoria"
  | "usuarios";

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
  { id: -1, nombre: "IVA 0%" },
  { id: -2, nombre: "IVA 19%" },
  { id: -3, nombre: "Exento" },
];

const AUDITORIA_PAGE_SIZE = 50;

export default function Configuracion() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const isAdmin = user?.role?.toUpperCase() === "ADMIN";
  const defaultTab: ConfigTab = "facturacion";
  const rawTab = searchParams.get("tab");
  const initialTab =
    (rawTab === "clave" ? "usuarios" : (rawTab as ConfigTab)) || defaultTab;

  const [activeTab, setActiveTab] = useState<ConfigTab>(initialTab);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa>(defaultEmpresa);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoRemoved, setLogoRemoved] = useState(false);
  const [facturacion, setFacturacion] =
    useState<ConfiguracionFacturacion>(defaultFacturacion);
  const [plantillaActiva] =
    useState<PlantillaField>("plantilla_factura_carta");
  const editorRef = useRef<HTMLDivElement | null>(null);
  const [impuestos, setImpuestos] = useState<Impuesto[]>(defaultImpuestos);
  const [auditoria, setAuditoria] = useState<AuditoriaRegistro[]>([]);
  const [auditoriaTotal, setAuditoriaTotal] = useState(0);
  const [auditoriaPage, setAuditoriaPage] = useState(1);
  const [auditoriaSearch, setAuditoriaSearch] = useState("");
  const [auditoriaFechaInicio, setAuditoriaFechaInicio] = useState("");
  const [auditoriaFechaFin, setAuditoriaFechaFin] = useState("");
  const [auditoriaRetention, setAuditoriaRetention] =
    useState<AuditoriaRetention | null>(null);
  const [auditoriaLoading, setAuditoriaLoading] = useState(false);
  const [auditoriaCleanupLoading, setAuditoriaCleanupLoading] = useState(false);
  const [auditoriaCleanupMessage, setAuditoriaCleanupMessage] = useState("");
  const [confirmAuditoriaCleanupOpen, setConfirmAuditoriaCleanupOpen] =
    useState(false);
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [mecanicosDisponibles, setMecanicosDisponibles] = useState<Mecanico[]>(
    []
  );
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [userModalMode, setUserModalMode] = useState<"create" | "edit">(
    "create"
  );
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [accessModalOpen, setAccessModalOpen] = useState(false);
  const [accessUsuario, setAccessUsuario] = useState<UsuarioAdmin | null>(null);
  const [accessSeleccionado, setAccessSeleccionado] =
    useState<ModuleAccessState>(createEmptyModuleAccess());
  const [mensajeAccesos, setMensajeAccesos] = useState("");
  const [accessLoading, setAccessLoading] = useState(false);
  const { showNotification } = useNotification();
  const [confirmUserDeleteOpen, setConfirmUserDeleteOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<UsuarioAdmin | null>(null);
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
    es_cajero: false,
    is_active: true,
    password: "",
  });
  const [nuevoImpuesto, setNuevoImpuesto] = useState<Partial<Impuesto>>({
    nombre: "",
  });

  const [mensajeEmpresa, setMensajeEmpresa] = useState("");
  const [mensajeFacturacion, setMensajeFacturacion] = useState("");
  const [mensajeImpuesto, setMensajeImpuesto] = useState("");
  const [mensajeUsuario, setMensajeUsuario] = useState("");
  const [mensajeNuevoUsuario, setMensajeNuevoUsuario] = useState("");

  const [confirmarNuevaClave, setConfirmarNuevaClave] = useState("");
  const [mostrarNuevaClave, setMostrarNuevaClave] = useState(false);
  const [mostrarConfirmarClave, setMostrarConfirmarClave] = useState(false);
  const [mostrarClaveCreacion, setMostrarClaveCreacion] = useState(false);

  const moduleAccess = useMemo(
    () =>
      isAdmin
        ? createEmptyModuleAccess()
        : normalizeModuleAccess(user?.modulos_permitidos ?? null),
    [isAdmin, user?.modulos_permitidos]
  );
  const configuracionSections =
    MODULE_DEFINITIONS.find((moduleDef) => moduleDef.key === "configuracion")
      ?.sections ?? [];
  const tabs = useMemo(() => {
    const visibleSections = isAdmin
      ? configuracionSections
      : configuracionSections.filter(
          (section) =>
            section.key !== "usuarios" &&
            isSectionEnabled(moduleAccess, "configuracion", section.key)
        );

    return visibleSections.map((section) => ({
      id: section.key as ConfigTab,
      label: section.label,
      icon:
        section.key === "facturacion" ? (
          <ShieldCheck size={18} />
        ) : section.key === "empresa" ? (
          <UserCog size={18} />
        ) : section.key === "usuarios" ? (
          <Users size={18} />
        ) : section.key === "impuestos" ? (
          <Plus size={18} />
        ) : (
          <Users size={18} />
        ),
    }));
  }, [configuracionSections, isAdmin, moduleAccess]);

  const canViewImpuestos =
    isAdmin || isSectionEnabled(moduleAccess, "configuracion", "impuestos");
  const canViewAuditoria =
    isAdmin || isSectionEnabled(moduleAccess, "configuracion", "auditoria");

  const availableTabs = useMemo(
    () => tabs.map((tab) => tab.id as ConfigTab),
    [tabs]
  );

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    const resolvedTab =
      tabParam === "clave" ? "usuarios" : (tabParam as ConfigTab | null);
    if (resolvedTab && availableTabs.includes(resolvedTab)) {
      if (resolvedTab !== activeTab) {
        setActiveTab(resolvedTab);
      }
      if (tabParam === "clave") {
        setSearchParams({ tab: "usuarios" });
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

      if (canViewImpuestos) {
        try {
          const data = await configuracionAPI.obtenerImpuestos();
          if (data?.length) {
            setImpuestos(data);
          }
        } catch (error) {
          console.error("Error cargando impuestos:", error);
        }
      }

    };

    cargarDatos();
  }, [canViewAuditoria, canViewImpuestos, isAdmin]);

  useEffect(() => {
    if (!canViewAuditoria) {
      return;
    }

    const cargarRetention = async () => {
      try {
        const data = await configuracionAPI.obtenerAuditoriaRetention();
        setAuditoriaRetention(data);
      } catch (error) {
        console.error("Error cargando retención de auditoría:", error);
      }
    };

    cargarRetention();
  }, [canViewAuditoria]);

  useEffect(() => {
    if (!canViewAuditoria) {
      return;
    }

    const cargarAuditoria = async () => {
      setAuditoriaLoading(true);
      try {
        const fechaInicio = auditoriaFechaInicio
          ? `${auditoriaFechaInicio}T00:00:00`
          : undefined;
        const fechaFin = auditoriaFechaFin
          ? `${auditoriaFechaFin}T23:59:59`
          : undefined;
        const data = await configuracionAPI.obtenerAuditoria({
          page: auditoriaPage,
          search: auditoriaSearch || undefined,
          fechaInicio,
          fechaFin,
        });
        setAuditoria(data.results);
        setAuditoriaTotal(data.count);
      } catch (error) {
        console.error("Error cargando auditoría:", error);
      } finally {
        setAuditoriaLoading(false);
      }
    };

    cargarAuditoria();
  }, [
    auditoriaFechaFin,
    auditoriaFechaInicio,
    auditoriaPage,
    auditoriaSearch,
    canViewAuditoria,
  ]);

  const limpiarAuditoria = async () => {
    setConfirmAuditoriaCleanupOpen(true);
  };

  const confirmLimpiarAuditoria = async () => {
    setAuditoriaCleanupLoading(true);
    setAuditoriaCleanupMessage("");
    try {
      const result = await configuracionAPI.archivarAuditoria();
      setAuditoriaCleanupMessage(
        `Archivados: ${result.archived}. Eliminados del histórico: ${result.purged}.`
      );
      setAuditoriaPage(1);
      showNotification({
        message: "Limpieza de auditoría completada.",
        type: "success",
      });
    } catch (error) {
      console.error("Error limpiando auditoría:", error);
      setAuditoriaCleanupMessage("No se pudo ejecutar la limpieza.");
      showNotification({
        message: "No se pudo ejecutar la limpieza.",
        type: "error",
      });
    } finally {
      setAuditoriaCleanupLoading(false);
      setConfirmAuditoriaCleanupOpen(false);
    }
  };

  const cargarUsuarios = useCallback(async () => {
    try {
      const data = await configuracionAPI.obtenerUsuarios();
      setUsuarios(data);
    } catch (error) {
      console.error("Error cargando usuarios:", error);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }

    cargarUsuarios();
  }, [cargarUsuarios, isAdmin]);

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
    if (!nuevoImpuesto.nombre) {
      setMensajeImpuesto("Completa el nombre del impuesto.");
      return;
    }

    try {
      const nuevo = await configuracionAPI.crearImpuesto({
        nombre: nuevoImpuesto.nombre,
      });
      setImpuestos((prev) => [...prev, nuevo]);
      setNuevoImpuesto({ nombre: "" });
      setMensajeImpuesto("Impuesto agregado correctamente.");
      showNotification({
        message: "Impuesto agregado correctamente.",
        type: "success",
      });
    } catch (error) {
      console.error("Error agregando impuesto:", error);
      setMensajeImpuesto("No se pudo agregar el impuesto.");
      showNotification({
        message: "No se pudo agregar el impuesto.",
        type: "error",
      });
    }
  };

  const handleEliminarImpuesto = async (impuesto: Impuesto) => {
    try {
      if (impuesto.id > 0) {
        await configuracionAPI.eliminarImpuesto(impuesto.id);
      }
      setImpuestos((prev) => prev.filter((item) => item.id !== impuesto.id));
      showNotification({
        message: "Impuesto eliminado correctamente.",
        type: "success",
      });
    } catch (error) {
      console.error("Error eliminando impuesto:", error);
      setMensajeImpuesto("No se pudo quitar el impuesto.");
      showNotification({
        message: "No se pudo quitar el impuesto.",
        type: "error",
      });
    }
  };

  const requestDeleteUsuario = (usuario: UsuarioAdmin) => {
    setUserToDelete(usuario);
    setConfirmUserDeleteOpen(true);
  };

  const confirmDeleteUsuario = async () => {
    if (!userToDelete) return;
    try {
      await usuariosApi.deleteUsuario(userToDelete.id);
      setUsuarios((prev) => prev.filter((item) => item.id !== userToDelete.id));
      setMensajeUsuario("Usuario eliminado correctamente.");
      showNotification({
        message: "Usuario eliminado correctamente.",
        type: "success",
      });
    } catch (error) {
      console.error("Error eliminando usuario:", error);
      setMensajeUsuario("No se pudo eliminar el usuario.");
      showNotification({
        message: "No se pudo eliminar el usuario.",
        type: "error",
      });
    } finally {
      setConfirmUserDeleteOpen(false);
      setUserToDelete(null);
    }
  };

  const openAccessModal = async (usuario: UsuarioAdmin) => {
    setAccessLoading(true);
    setAccessUsuario(usuario);
    setAccessSeleccionado(
      normalizeModuleAccess(usuario.modulos_permitidos ?? null)
    );
    setMensajeAccesos("");
    setAccessModalOpen(true);

    try {
      const data = await configuracionAPI.obtenerUsuario(usuario.id);
      setAccessUsuario(data);
      setAccessSeleccionado(
        normalizeModuleAccess(data.modulos_permitidos ?? null)
      );
    } catch (error) {
      console.error("Error cargando accesos del usuario:", error);
      setMensajeAccesos("No se pudieron cargar los accesos actuales.");
    } finally {
      setAccessLoading(false);
    }
  };

  const closeAccessModal = () => {
    setAccessModalOpen(false);
    setAccessUsuario(null);
    setAccessSeleccionado(createEmptyModuleAccess());
    setMensajeAccesos("");
  };

  const toggleAccessModule = (moduleKey: string, enabled: boolean) => {
    setAccessSeleccionado((prev) => {
      const moduleDef = MODULE_DEFINITIONS.find(
        (definition) => definition.key === moduleKey
      );
      if (!moduleDef) {
        return prev;
      }
      const current = prev[moduleKey];
      const nextSections = { ...current.sections };
      (moduleDef.sections ?? []).forEach((section) => {
        nextSections[section.key] = enabled;
      });
      return {
        ...prev,
        [moduleKey]: {
          ...current,
          enabled,
          sections: nextSections,
        },
      };
    });
  };

  const toggleAccessSection = (
    moduleKey: string,
    sectionKey: string,
    enabled: boolean
  ) => {
    setAccessSeleccionado((prev) => {
      const current = prev[moduleKey];
      if (!current) {
        return prev;
      }
      const nextSections = {
        ...current.sections,
        [sectionKey]: enabled,
      };
      const hasAnySelected = Object.values(nextSections).some(Boolean);
      return {
        ...prev,
        [moduleKey]: {
          ...current,
          enabled: hasAnySelected,
          sections: nextSections,
        },
      };
    });
  };

  const handleGuardarAccesos = async () => {
    if (!accessUsuario) {
      return;
    }
    setMensajeAccesos("");
    try {
      const data = await configuracionAPI.actualizarUsuario(accessUsuario.id, {
        modulos_permitidos: accessSeleccionado,
      });
      setUsuarios((prev) =>
        prev.map((item) =>
          item.id === data.id
            ? { ...item, modulos_permitidos: data.modulos_permitidos ?? null }
            : item
        )
      );
      closeAccessModal();
      setMensajeUsuario("Accesos actualizados correctamente.");
    } catch (error) {
      console.error("Error actualizando accesos:", error);
      setMensajeAccesos("No se pudieron guardar los accesos.");
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
      es_cajero: false,
      is_active: true,
      password: "",
    });
    setConfirmarNuevaClave("");
    setMostrarNuevaClave(false);
    setMostrarConfirmarClave(false);
    setMostrarClaveCreacion(false);
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
      es_cajero: usuario.es_cajero ?? false,
      is_active: usuario.is_active,
      password: "",
    });
    setConfirmarNuevaClave("");
    setMostrarNuevaClave(false);
    setMostrarConfirmarClave(false);
    setMensajeNuevoUsuario("");
    setUserModalOpen(true);
  };

  const handleGuardarUsuarioModal = async () => {
    if (!nuevoUsuario.username || !nuevoUsuario.tipo_usuario) {
      setMensajeNuevoUsuario("Completa el usuario y el rol para continuar.");
      return;
    }

    if (userModalMode === "create") {
      if (!nuevoUsuario.password) {
        setMensajeNuevoUsuario("Debes asignar una contraseña al usuario.");
        return;
      }
    } else if (nuevoUsuario.password && nuevoUsuario.password !== confirmarNuevaClave) {
      setMensajeNuevoUsuario("La nueva clave y la confirmación no coinciden.");
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
          es_cajero: nuevoUsuario.es_cajero,
          is_active: nuevoUsuario.is_active,
          password: nuevoUsuario.password,
        };
        const data = await configuracionAPI.crearUsuario(payload);
        setUsuarios((prev) => [data, ...prev]);
        setMensajeNuevoUsuario("Usuario creado correctamente.");
        showNotification({
          message: "Usuario creado correctamente.",
          type: "success",
        });
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
          es_cajero: nuevoUsuario.es_cajero,
          is_active: nuevoUsuario.is_active,
        };
        const data = await configuracionAPI.actualizarUsuario(
          editingUserId,
          payload
        );
        if (nuevoUsuario.password) {
          await configuracionAPI.cambiarClave(
            editingUserId,
            nuevoUsuario.password
          );
        }
        setUsuarios((prev) =>
          prev.map((item) => (item.id === data.id ? data : item))
        );
        setMensajeNuevoUsuario("Usuario actualizado correctamente.");
        showNotification({
          message: "Usuario actualizado correctamente.",
          type: "success",
        });
      }
      setUserModalOpen(false);
      resetNuevoUsuario();
    } catch (error) {
      console.error("Error guardando usuario:", error);
      setMensajeNuevoUsuario("No se pudo guardar el usuario.");
      showNotification({
        message: "No se pudo guardar el usuario.",
        type: "error",
      });
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
                Gestiona los impuestos del sistema
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

          {/* Tabla de impuestos */}
          <div className="mt-6 overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Impuesto
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {impuestos.map((impuesto) => {
                  const esFijo = impuesto.id < 0; // IDs negativos son impuestos por defecto
                  return (
                    <tr key={impuesto.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          {esFijo && (
                            <Lock size={14} className="text-slate-400" />
                          )}
                          <span className="text-sm font-medium text-slate-900">
                            {impuesto.nombre}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center whitespace-nowrap">
                        {!esFijo && (
                          <button
                            type="button"
                            onClick={() => handleEliminarImpuesto(impuesto)}
                            className="inline-flex items-center justify-center rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                            title="Eliminar impuesto"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                        {esFijo && (
                          <span className="text-xs text-slate-400">Fijo</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Formulario para agregar impuesto */}
          <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <h4 className="text-sm font-semibold text-slate-700 mb-4">
              Agregar nuevo impuesto
            </h4>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">
                  Nombre
                </label>
                <input
                  type="text"
                  value={nuevoImpuesto.nombre}
                  onChange={(event) =>
                    setNuevoImpuesto((prev) => ({
                      ...prev,
                      nombre: event.target.value,
                    }))
                  }
                  placeholder="Ej: IVA 19%, IVA 5%, Exento"
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={handleAgregarImpuesto}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                >
                  <Plus size={16} /> Agregar
                </button>
              </div>
            </div>
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
          {auditoriaRetention && (
            <p className="mt-2 text-xs text-slate-500">
              Se conservan {auditoriaRetention.retention_days} días en la
              auditoría activa y {auditoriaRetention.archive_retention_days}{" "}
              días en el archivo histórico.
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={limpiarAuditoria}
              disabled={auditoriaCleanupLoading}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm hover:border-slate-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {auditoriaCleanupLoading ? "Limpiando..." : "Limpiar auditoría"}
            </button>
            {auditoriaCleanupMessage && (
              <span className="text-xs text-slate-500">
                {auditoriaCleanupMessage}
              </span>
            )}
          </div>

          <div className="mt-5 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4">
            <label className="space-y-1 text-xs font-semibold text-slate-600">
              Buscar
              <input
                value={auditoriaSearch}
                onChange={(event) => {
                  setAuditoriaSearch(event.target.value);
                  setAuditoriaPage(1);
                }}
                placeholder="Usuario, acción o notas"
                className="w-64 rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-700"
              />
            </label>
            <label className="space-y-1 text-xs font-semibold text-slate-600">
              Desde
              <input
                type="date"
                value={auditoriaFechaInicio}
                onChange={(event) => {
                  setAuditoriaFechaInicio(event.target.value);
                  setAuditoriaPage(1);
                }}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-700"
              />
            </label>
            <label className="space-y-1 text-xs font-semibold text-slate-600">
              Hasta
              <input
                type="date"
                value={auditoriaFechaFin}
                onChange={(event) => {
                  setAuditoriaFechaFin(event.target.value);
                  setAuditoriaPage(1);
                }}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-700"
              />
            </label>
            <div className="ml-auto text-xs text-slate-500">
              {auditoriaTotal > 0
                ? `Total registros: ${auditoriaTotal}`
                : "Sin registros"}
            </div>
          </div>

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
                {auditoriaLoading ? (
                  <tr>
                    <td className="px-4 py-4 text-slate-500" colSpan={4}>
                      Cargando auditoría...
                    </td>
                  </tr>
                ) : auditoria.length === 0 ? (
                  <tr>
                    <td className="px-4 py-4 text-slate-500" colSpan={4}>
                      Aún no hay movimientos registrados.
                    </td>
                  </tr>
                ) : (
                  auditoria.map((registro) => (
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

          <div className="mt-4 text-xs text-slate-500">
            <Pagination
              page={auditoriaPage}
              totalPages={Math.max(1, Math.ceil(auditoriaTotal / AUDITORIA_PAGE_SIZE))}
              onPageChange={setAuditoriaPage}
              size="sm"
              className="text-slate-500"
            />
          </div>
        </section>
      )}

      {activeTab === "usuarios" && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900">
            Usuarios
          </h3>
          <p className="text-sm text-slate-500">
            Administra usuarios desde esta sección.
          </p>

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
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600">
                          {usuario.tipo_usuario === "ADMIN"
                            ? "Administrador"
                            : usuario.tipo_usuario === "VENDEDOR"
                            ? "Vendedor"
                            : usuario.tipo_usuario === "MECANICO"
                            ? "Mecánico"
                            : "Bodeguero"}
                        </span>
                        {usuario.es_cajero && (
                          <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                            Caja
                          </span>
                        )}
                      </div>
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
                        onClick={() => requestDeleteUsuario(usuario)}
                        className="rounded-lg bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700"
                      >
                        Eliminar
                      </button>
                      <button
                        type="button"
                        onClick={() => openEditUserModal(usuario)}
                        className="ml-2 rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 hover:border-blue-200 hover:text-blue-600"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        onClick={() => openAccessModal(usuario)}
                        className="ml-2 rounded-lg border border-blue-200 px-3 py-1 text-xs font-medium text-blue-600 hover:border-blue-300 hover:text-blue-700"
                      >
                        Accesos
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
                <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={nuevoUsuario.es_cajero}
                    onChange={(event) =>
                      setNuevoUsuario((prev) => ({
                        ...prev,
                        es_cajero: event.target.checked,
                      }))
                    }
                  />
                  Asignar perfil de caja
                </label>
                {userModalMode === "edit" ? (
                  <>
                    <label className="space-y-2 text-xs font-medium text-slate-700">
                      Nueva clave
                      <div className="flex items-center gap-2">
                        <input
                          type={mostrarNuevaClave ? "text" : "password"}
                          value={nuevoUsuario.password}
                          onChange={(event) =>
                            setNuevoUsuario((prev) => ({
                              ...prev,
                              password: event.target.value,
                            }))
                          }
                          placeholder="Ingresa una nueva clave"
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setMostrarNuevaClave((prev) => !prev)
                          }
                          className="rounded-lg border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:border-blue-200 hover:text-blue-600"
                          aria-label={
                            mostrarNuevaClave
                              ? "Ocultar clave"
                              : "Mostrar clave"
                          }
                        >
                          {mostrarNuevaClave ? (
                            <EyeOff size={14} />
                          ) : (
                            <Eye size={14} />
                          )}
                        </button>
                      </div>
                      <p className="text-[11px] font-normal text-slate-500">
                        Deja en blanco para mantener la clave actual.
                      </p>
                    </label>
                    <label className="space-y-2 text-xs font-medium text-slate-700">
                      Confirmar nueva clave
                      <div className="flex items-center gap-2">
                        <input
                          type={mostrarConfirmarClave ? "text" : "password"}
                          value={confirmarNuevaClave}
                          onChange={(event) =>
                            setConfirmarNuevaClave(event.target.value)
                          }
                          placeholder="Repite la nueva clave"
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setMostrarConfirmarClave((prev) => !prev)
                          }
                          className="rounded-lg border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:border-blue-200 hover:text-blue-600"
                          aria-label={
                            mostrarConfirmarClave
                              ? "Ocultar clave"
                              : "Mostrar clave"
                          }
                        >
                          {mostrarConfirmarClave ? (
                            <EyeOff size={14} />
                          ) : (
                            <Eye size={14} />
                          )}
                        </button>
                      </div>
                    </label>
                  </>
                ) : (
                  <label className="space-y-2 text-xs font-medium text-slate-700">
                    Contraseña
                    <div className="flex items-center gap-2">
                      <input
                        type={mostrarClaveCreacion ? "text" : "password"}
                        value={nuevoUsuario.password}
                        onChange={(event) =>
                          setNuevoUsuario((prev) => ({
                            ...prev,
                            password: event.target.value,
                          }))
                        }
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setMostrarClaveCreacion((prev) => !prev)
                        }
                        className="rounded-lg border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:border-blue-200 hover:text-blue-600"
                        aria-label={
                          mostrarClaveCreacion
                            ? "Ocultar clave"
                            : "Mostrar clave"
                        }
                      >
                        {mostrarClaveCreacion ? (
                          <EyeOff size={14} />
                        ) : (
                          <Eye size={14} />
                        )}
                      </button>
                    </div>
                  </label>
                )}
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

      {accessModalOpen && accessUsuario && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4 py-6">
          <div className="w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs font-semibold uppercase text-blue-500">
                  Accesos por módulos
                </p>
                <h2 className="text-lg font-semibold text-slate-900">
                  Accesos de {accessUsuario.username}
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
              {mensajeAccesos && (
                <div className="rounded-lg border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                  {mensajeAccesos}
                </div>
              )}
              {accessLoading && (
                <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                  Cargando accesos del usuario...
                </div>
              )}
              <p className="text-sm text-slate-600">
                Activa o desactiva los módulos disponibles para este usuario.
              </p>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {MODULE_DEFINITIONS.map((moduleDef) => {
                  const moduleState = accessSeleccionado[moduleDef.key];
                  const totalSections =
                    moduleDef.sections && moduleDef.sections.length > 0
                      ? moduleDef.sections.length
                      : 1;
                  const selectedSections =
                    moduleDef.sections && moduleDef.sections.length > 0
                      ? moduleDef.sections.filter(
                          (section) => moduleState.sections[section.key]
                        ).length
                      : moduleState.enabled
                      ? 1
                      : 0;

                  return (
                    <div
                      key={moduleDef.key}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-4 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-sm font-semibold text-slate-800">
                            {moduleDef.label}
                          </h3>
                          {moduleDef.description && (
                            <p className="text-xs text-slate-500">
                              {moduleDef.description}
                            </p>
                          )}
                          <p className="mt-2 text-xs text-slate-400">
                            Seleccionadas: {selectedSections}/{totalSections}
                          </p>
                        </div>
                        <input
                          type="checkbox"
                          checked={moduleState.enabled}
                          onChange={(event) =>
                            toggleAccessModule(
                              moduleDef.key,
                              event.target.checked
                            )
                          }
                        />
                      </div>
                      {moduleDef.sections && moduleDef.sections.length > 0 && (
                        <div className="mt-4 space-y-2 border-t border-slate-200 pt-3">
                          {moduleDef.sections.map((section) => (
                            <label
                              key={section.key}
                              className="flex items-center justify-between text-xs text-slate-600"
                            >
                              {section.label}
                              <input
                                type="checkbox"
                                checked={moduleState.sections[section.key]}
                                onChange={(event) =>
                                  toggleAccessSection(
                                    moduleDef.key,
                                    section.key,
                                    event.target.checked
                                  )
                                }
                              />
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
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
      <ConfirmModal
        open={confirmAuditoriaCleanupOpen}
        title="Limpiar auditoría"
        description="Esto archivará los registros antiguos y limpiará el histórico según la política de retención. ¿Deseas continuar?"
        confirmLabel="Continuar"
        confirmVariant="danger"
        onConfirm={confirmLimpiarAuditoria}
        onCancel={() => setConfirmAuditoriaCleanupOpen(false)}
        loading={auditoriaCleanupLoading}
      />
      <ConfirmModal
        open={confirmUserDeleteOpen}
        title="Eliminar usuario"
        description={
          userToDelete
            ? `Se eliminará el usuario ${userToDelete.username}. ¿Deseas continuar?`
            : "¿Deseas continuar?"
        }
        confirmLabel="Eliminar"
        confirmVariant="danger"
        onConfirm={confirmDeleteUsuario}
        onCancel={() => {
          setConfirmUserDeleteOpen(false);
          setUserToDelete(null);
        }}
      />
    </div>
  );
}
