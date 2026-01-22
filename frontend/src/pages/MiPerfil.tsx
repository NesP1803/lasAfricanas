import { useEffect, useState } from "react";
import { Eye, EyeOff, Save } from "lucide-react";
import { configuracionAPI } from "../api/configuracion";
import { useAuth } from "../contexts/AuthContext";
import type { UsuarioAdmin } from "../types";

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
  const [perfil, setPerfil] = useState<UsuarioAdmin | null>(null);
  const [form, setForm] = useState<PerfilForm>(emptyPerfil);
  const [mensajePerfil, setMensajePerfil] = useState("");
  const [mensajeClave, setMensajeClave] = useState("");
  const [claveActual, setClaveActual] = useState("");
  const [nuevaClave, setNuevaClave] = useState("");
  const [confirmarClave, setConfirmarClave] = useState("");
  const [mostrarClaveActual, setMostrarClaveActual] = useState(false);
  const [mostrarNuevaClave, setMostrarNuevaClave] = useState(false);
  const [mostrarConfirmarClave, setMostrarConfirmarClave] = useState(false);

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

    if (!claveActual) {
      setMensajeClave("Debes ingresar tu clave actual.");
      return;
    }

    if (!nuevaClave || nuevaClave !== confirmarClave) {
      setMensajeClave("La nueva clave y la confirmación no coinciden.");
      return;
    }

    try {
      await configuracionAPI.cambiarClave(perfil?.id ?? user!.id, nuevaClave);
      setClaveActual("");
      setNuevaClave("");
      setConfirmarClave("");
      setMensajeClave("La clave ha sido actualizada correctamente.");
    } catch (error) {
      console.error("Error cambiando clave:", error);
      setMensajeClave("No se pudo actualizar la clave.");
    }
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

      <section className="rounded-2xl bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Cambiar contraseña
            </h3>
            <p className="text-sm text-slate-500">
              Ingresa tu clave actual y define una nueva contraseña.
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

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <label className="space-y-2 text-sm font-medium text-slate-700">
            Clave actual
            <div className="flex items-center gap-2">
              <input
                type={mostrarClaveActual ? "text" : "password"}
                value={claveActual}
                onChange={(event) => setClaveActual(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => setMostrarClaveActual((prev) => !prev)}
                className="rounded-lg border border-slate-200 px-2 py-2 text-xs font-semibold text-slate-600 hover:border-blue-200 hover:text-blue-600"
                aria-label={
                  mostrarClaveActual ? "Ocultar clave" : "Mostrar clave"
                }
              >
                {mostrarClaveActual ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </label>
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
