import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useNotification } from "../contexts/NotificationContext";
import { descuentosApi, type SolicitudDescuento } from "../api/descuentos";

export default function Notificaciones() {
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const navigate = useNavigate();
  const [solicitudes, setSolicitudes] = useState<SolicitudDescuento[]>([]);
  const [ajustesDescuento, setAjustesDescuento] = useState<Record<string, string>>({});
  const lastSolicitudFetchRef = useRef(0);

  const esAdmin = useMemo(() => user?.role === "ADMIN", [user?.role]);
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
    if (!esAdmin) {
      navigate("/mi-perfil", { replace: true });
    }
  }, [esAdmin, navigate]);

  const actualizarSolicitudes = useCallback(async () => {
    if (!esAdmin || !user?.id) {
      setSolicitudes([]);
      return;
    }
    const now = Date.now();
    if (now - lastSolicitudFetchRef.current < 10000) {
      return;
    }
    lastSolicitudFetchRef.current = now;
    try {
      const data = await descuentosApi.listarSolicitudes();
      setSolicitudes(data);
      const pendientes = data.filter((solicitud) => solicitud.estado === "PENDIENTE");
      if (pendientes.length > 0) {
        showNotification({
          type: "info",
          message: `Tienes ${pendientes.length} solicitud(es) de descuento pendientes.`,
        });
      }
    } catch (error) {
      showNotification({
        type: "error",
        message: "No se pudieron cargar las solicitudes.",
      });
    }
  }, [esAdmin, showNotification, user?.id]);

  useEffect(() => {
    actualizarSolicitudes();
  }, [actualizarSolicitudes]);

  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        actualizarSolicitudes();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [actualizarSolicitudes]);

  const handleAjusteDescuento = (id: string, value: string) => {
    setAjustesDescuento((prev) => ({ ...prev, [id]: value }));
  };

  const handleResolverSolicitud = (
    solicitud: SolicitudDescuento,
    estado: "APROBADO" | "RECHAZADO"
  ) => {
    const valorAprobado = ajustesDescuento[solicitud.id];
    const descuentoAprobado = Number(
      valorAprobado === undefined || valorAprobado === ""
        ? solicitud.descuento_solicitado
        : valorAprobado
    );
    descuentosApi
      .actualizarSolicitud(solicitud.id, {
        estado,
        descuento_aprobado: estado === "APROBADO" ? String(descuentoAprobado) : null,
      })
      .then(() => descuentosApi.listarSolicitudes())
      .then((data) => setSolicitudes(data))
      .catch(() => {
        showNotification({
          type: "error",
          message: "No se pudo actualizar la solicitud.",
        });
      });
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
        <h2 className="text-2xl font-semibold text-slate-900">Notificaciones</h2>
        <p className="mt-1 text-sm text-slate-500">
          Gestiona las solicitudes de descuento recibidas por tu equipo.
        </p>
      </div>

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
          <button
            type="button"
            onClick={actualizarSolicitudes}
            className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50"
          >
            Actualizar
          </button>
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
                      {solicitud.vendedor_nombre}
                    </p>
                    <p className="text-xs text-slate-500">
                      Solicitó {solicitud.descuento_solicitado}% · Estado:{" "}
                      <span className="font-semibold">{solicitud.estado}</span>
                    </p>
                    {solicitud.descuento_aprobado && (
                      <p className="text-xs text-slate-500">
                        Descuento aprobado: {solicitud.descuento_aprobado}%
                      </p>
                    )}
                    {solicitud.total_con_descuento !== null &&
                      solicitud.total_con_descuento !== undefined &&
                      solicitud.total_antes_descuento !== null &&
                      solicitud.total_antes_descuento !== undefined && (
                        <p className="text-xs text-slate-500">
                          Total antes: {currencyFormatter.format(Number(solicitud.total_antes_descuento))} ·
                          Total solicitado: {currencyFormatter.format(Number(solicitud.total_con_descuento))}
                        </p>
                      )}
                  </div>
                  <div className="text-xs text-slate-500">
                    {new Date(solicitud.updated_at).toLocaleString()}
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
                        value={ajustesDescuento[solicitud.id] ?? String(solicitud.descuento_solicitado)}
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
    </div>
  );
}
