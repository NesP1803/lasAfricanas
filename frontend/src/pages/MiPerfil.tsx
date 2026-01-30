import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Eye, EyeOff, Save, XCircle } from "lucide-react";
import { configuracionAPI } from "../api/configuracion";
import { useAuth } from "../contexts/AuthContext";
import { useNotification } from "../contexts/NotificationContext";
import type { UsuarioAdmin } from "../types";
import {
  actualizarSolicitud,
  obtenerSolicitudesPorAprobador,
  type SolicitudDescuento,
} from "../utils/descuentos";

type PerfilForm = Pick<
  UsuarioAdmin,
  "email" | "first_name" | "last_name" | "telefono" | "sede"
>;

const emptyPerfil: PerfilForm = {
  email: "",
  first_name: "",
  last_name: "",
  telefono: "",
  sede: "",
};

export default function MiPerfil() {
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const [perfil, setPerfil] = useState<UsuarioAdmin | null>(null);
  const [form, setForm] = useState<PerfilForm>(emptyPerfil);
  const [mensajePerfil, setMensajePerfil] = useState("");
  const [mensajeClave, setMensajeClave] = useState("");
  const [nuevaClave, setNuevaClave] = useState("");
  const [confirmarClave, setConfirmarClave] = useState("");
  const [mostrarNuevaClave, setMostrarNuevaClave] = useState(false);
  const [mostrarConfirmarClave, setMostrarConfirmarClave] = useState(false);
  const [solicitudes, setSolicitudes] = useState<SolicitudDescuento[]>([]);
  const [ajustesDescuento, setAjustesDescuento] = useState<Record<string, string>>({});

  const esAdmin = useMemo(() => {
    return (perfil?.tipo_usuario ?? user?.role) === "ADMIN";
  }, [perfil?.tipo_usuario, user?.role]);

  const currencyFormatter = useMemo(
    () =>
      new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        minimumFractionDigits: 2,
      }),
    []
  );

  useEffect(() => {
    const cargarPerfil = async () => {
      try {
        const data = await configuracionAPI.obtenerUsuarioActual();
        setPerfil(data);
        setForm({
          email: data.email || "",
          first_name: data.first_name || "",
          last_name: data.last_name || "",
          telefono: data.telefono || "",
          sede: data.sede || "",
        });
      } catch (error) {
        console.error("Error cargando perfil:", error);
      }
    };

    cargarPerfil();
  }, []);

  useEffect(() => {
    if (!esAdmin || !user?.id) {
      setSolicitudes([]);
      return;
    }
    const actualizarSolicitudes = () => {
      const data = obtenerSolicitudesPorAprobador(user.id);
      setSolicitudes(data);
      const pendientes = data.filter((solicitud) => solicitud.estado === "PENDIENTE");
      if (pendientes.length > 0) {
        showNotification({
          type: "info",
          message: `Tienes ${pendientes.length} solicitud(es) de descuento pendientes.`,
        });
      }
    };

    actualizarSolicitudes();
    const handleStorage = (event: StorageEvent) => {
      if (event.key === "solicitudes_descuento") {
        actualizarSolicitudes();
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [esAdmin, showNotification, user?.id]);

  const handleGuardarPerfil = async () => {
    setMensajePerfil("");
    try {
      const data = await configuracionAPI.actualizarUsuarioActual(form);
      setPerfil(data);
      setForm({
        email: data.email || "",
        first_name: data.first_name || "",
        last_name: data.last_name || "",
        telefono: data.telefono || "",
        sede: data.sede || "",
      });
      setMensajePerfil("Datos actualizados correctamente.");
    } catch (error) {
      console.error("Error actualizando perfil:", error);
      setMensajePerfil("No se pudieron guardar los cambios.");
    }
  };

  const handleCambiarClave = async () => {
    if (!perfil?.id && !user?.id) {
      setMensajeClave("No se pudo identificar el usuario.");
      return;
    }

    if (!nuevaClave || nuevaClave !== confirmarClave) {
      setMensajeClave("La nueva clave y la confirmación no coinciden.");
      return;
    }

    try {
      await configuracionAPI.cambiarClave(perfil?.id ?? user!.id, nuevaClave);
      setNuevaClave("");
      setConfirmarClave("");
      setMensajeClave("La clave ha sido actualizada correctamente.");
    } catch (error) {
      console.error("Error cambiando clave:", error);
      setMensajeClave("No se pudo actualizar la clave.");
    }
  };

  const handleAjusteDescuento = (id: string, value: string) => {
    setAjustesDescuento((prev) => ({ ...prev, [id]: value }));
  };

  const handleResolverSolicitud = (solicitud: SolicitudDescuento, estado: "APROBADO" | "RECHAZADO") => {
    const valorAprobado = ajustesDescuento[solicitud.id];
    const descuentoAprobado = Number(
      valorAprobado === undefined || valorAprobado === "" ? solicitud.descuentoSolicitado : valorAprobado
    );
    const updated = actualizarSolicitud(solicitud.id, {
      estado,
      descuentoAprobado: estado === "APROBADO" ? descuentoAprobado : undefined,
    });
    setSolicitudes(updated.filter((item) => item.aprobadorId === solicitud.aprobadorId));
    showNotification({
      type: estado === "APROBADO" ? "success" : "error",
      message:
        estado === "APROBADO"
          ? `Solicitud aprobada en ${descuentoAprobado}%.`
          : "Solicitud de descuento rechazada.",
    });
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-semibold text-slate-900">Mi perfil</h2>
        <p className="mt-1 text-sm text-slate-500">
          Revisa tus datos personales y actualiza tu contraseña.
        </p>
      </div>

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Datos personales
            </h3>
            <p className="text-sm text-slate-500">
              Actualiza tu información básica de contacto.
            </p>
          </div>
          <button
            type="button"
            onClick={handleGuardarPerfil}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700"
          >
            <Save size={16} /> Guardar
          </button>
        </div>

        {mensajePerfil && (
          <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {mensajePerfil}
          </div>
        )}

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Usuario
            <input
              value={perfil?.username ?? user?.username ?? ""}
              readOnly
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-500"
            />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Email
            <input
              value={form.email}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, email: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Teléfono
            <input
              value={form.telefono || ""}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, telefono: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Nombre
            <input
              value={form.first_name}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, first_name: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Apellido
            <input
              value={form.last_name}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, last_name: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Sede
            <input
              value={form.sede || ""}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, sede: event.target.value }))
              }
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
        </div>
      </section>

      {esAdmin && (
        <section className="rounded-2xl bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                Solicitudes de descuento
              </h3>
              <p className="text-sm text-slate-500">
                Revisa y autoriza descuentos solicitados por otros usuarios.
              </p>
            </div>
          </div>

          {solicitudes.length === 0 ? (
            <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              No hay solicitudes pendientes ni aprobadas.
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              {solicitudes.map((solicitud) => (
                <div
                  key={solicitud.id}
                  className="rounded-xl border border-slate-200 p-4 text-sm"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="font-semibold text-slate-800">
                        {solicitud.solicitanteNombre}
                      </p>
                      <p className="text-xs text-slate-500">
                        Solicitó {solicitud.descuentoSolicitado}% · Estado:{" "}
                        <span className="font-semibold">{solicitud.estado}</span>
                      </p>
                      {solicitud.descuentoAprobado !== undefined && (
                        <p className="text-xs text-slate-500">
                          Descuento aprobado: {solicitud.descuentoAprobado}%
                        </p>
                      )}
                      {solicitud.totalConDescuento !== undefined &&
                        solicitud.totalAntesDescuento !== undefined && (
                          <p className="text-xs text-slate-500">
                            Total antes: {currencyFormatter.format(solicitud.totalAntesDescuento)} ·
                            Total solicitado: {currencyFormatter.format(solicitud.totalConDescuento)}
                          </p>
                        )}
                    </div>
                    <div className="text-xs text-slate-500">
                      {new Date(solicitud.updatedAt).toLocaleString()}
                    </div>
                  </div>

                  {solicitud.estado === "PENDIENTE" && (
                    <div className="mt-4 grid gap-3 md:grid-cols-[200px,1fr] md:items-center">
                      <label className="text-xs font-semibold uppercase text-slate-500">
                        Ajustar descuento (%)
                      </label>
                      <div className="flex flex-wrap items-center gap-3">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={ajustesDescuento[solicitud.id] ?? String(solicitud.descuentoSolicitado)}
                          onChange={(event) =>
                            handleAjusteDescuento(solicitud.id, event.target.value)
                          }
                          className="w-28 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => handleResolverSolicitud(solicitud, "APROBADO")}
                          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold uppercase text-white hover:bg-emerald-700"
                        >
                          <CheckCircle2 size={16} /> Aprobar
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResolverSolicitud(solicitud, "RECHAZADO")}
                          className="inline-flex items-center gap-2 rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold uppercase text-rose-600 hover:bg-rose-50"
                        >
                          <XCircle size={16} /> Rechazar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Cambiar contraseña
            </h3>
            <p className="text-sm text-slate-500">
              Define una nueva contraseña para tu cuenta.
            </p>
          </div>
          <button
            type="button"
            onClick={handleCambiarClave}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700"
          >
            <Save size={16} /> Guardar clave
          </button>
        </div>

        {mensajeClave && (
          <div className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {mensajeClave}
          </div>
        )}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Nueva clave
            <div className="flex items-center gap-2">
              <input
                type={mostrarNuevaClave ? "text" : "password"}
                value={nuevaClave}
                onChange={(event) => setNuevaClave(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => setMostrarNuevaClave((prev) => !prev)}
                className="rounded-lg border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:border-blue-200 hover:text-blue-600"
                aria-label={
                  mostrarNuevaClave ? "Ocultar clave" : "Mostrar clave"
                }
              >
                {mostrarNuevaClave ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </label>
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Confirmar nueva clave
            <div className="flex items-center gap-2">
              <input
                type={mostrarConfirmarClave ? "text" : "password"}
                value={confirmarClave}
                onChange={(event) => setConfirmarClave(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => setMostrarConfirmarClave((prev) => !prev)}
                className="rounded-lg border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:border-blue-200 hover:text-blue-600"
                aria-label={
                  mostrarConfirmarClave ? "Ocultar clave" : "Mostrar clave"
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
        </div>
      </section>
    </div>
  );
}
