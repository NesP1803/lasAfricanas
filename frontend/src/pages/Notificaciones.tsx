import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useNotification } from "../contexts/NotificationContext";
import {
  actualizarSolicitud,
  obtenerSolicitudesPorAprobador,
  type SolicitudDescuento,
} from "../utils/descuentos";

export default function Notificaciones() {
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const navigate = useNavigate();
  const [solicitudes, setSolicitudes] = useState<SolicitudDescuento[]>([]);
  const [ajustesDescuento, setAjustesDescuento] = useState<Record<string, string>>({});

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
        ? solicitud.descuentoSolicitado
        : valorAprobado
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
    </div>
  );
}
