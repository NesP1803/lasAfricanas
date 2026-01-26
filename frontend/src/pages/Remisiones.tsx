import { useEffect, useMemo, useState } from 'react';
import {
  FileSearch,
  Printer,
  FileText,
  Ban,
  Eye,
  X,
  ChevronDown,
} from 'lucide-react';
import { ventasApi, type VentaListItem } from '../api/ventas';

type DocumentoTipo = 'POS' | 'CARTA';

type RemisionItem = {
  id: number;
  prefijo: string;
  numero: string;
  fechaHora: string;
  fechaIso: string;
  estado: string;
  estadoDisplay: string;
  medioPago: string;
  medioPagoDisplay: string;
  total: number;
  nitCc: string;
  cliente: string;
  usuario: string;
};

type DocumentoSeleccionado = {
  remision: RemisionItem;
  tipo: DocumentoTipo;
};

type AnulacionData = {
  motivo: string;
  numeroNuevaRemision: string;
  opcion: 'ANULAR_TODO' | 'USAR_DATOS';
};

const motivosAnulacion = [
  { value: 'DEVOLUCION_PARCIAL', label: 'Devolución parcial' },
  { value: 'DEVOLUCION_TOTAL', label: 'Devolución total' },
  { value: 'ERROR_PRECIOS', label: 'Error con precios en la remisión' },
  { value: 'ERROR_CONCEPTO', label: 'Error por conceptos en la remisión' },
  { value: 'COMPRADOR_NO_ACEPTA', label: 'El comprador no acepta los artículos' },
  { value: 'OTRO', label: 'Otro' },
];

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
});

const formatFechaHora = (fechaIso: string) => {
  const date = new Date(fechaIso);
  if (Number.isNaN(date.getTime())) return fechaIso;
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const splitNumeroComprobante = (numeroComprobante: string) => {
  const [prefijo, ...rest] = numeroComprobante.split('-');
  if (rest.length === 0) {
    return { prefijo: numeroComprobante.slice(0, 3), numero: numeroComprobante };
  }
  return { prefijo, numero: rest.join('-') };
};

const mapVentaToRemisionItem = (venta: VentaListItem): RemisionItem => {
  const { prefijo, numero } = splitNumeroComprobante(venta.numero_comprobante);
  return {
    id: venta.id,
    prefijo,
    numero,
    fechaHora: formatFechaHora(venta.fecha),
    fechaIso: venta.fecha,
    estado: venta.estado,
    estadoDisplay: venta.estado_display,
    medioPago: venta.medio_pago,
    medioPagoDisplay: venta.medio_pago_display,
    total: Number(venta.total),
    nitCc: venta.cliente_numero_documento,
    cliente: venta.cliente_nombre,
    usuario: venta.vendedor_nombre,
  };
};

export default function Remisiones() {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [remisiones, setRemisiones] = useState<RemisionItem[]>([]);
  const [busqueda, setBusqueda] = useState('');
  const [estadoFiltro, setEstadoFiltro] = useState<'CONFIRMADA' | 'ANULADA' | 'TODAS'>(
    'CONFIRMADA'
  );
  const [fechaInicio, setFechaInicio] = useState('2025-10-22');
  const [fechaFin, setFechaFin] = useState('2025-10-22');
  const [documento, setDocumento] = useState<DocumentoSeleccionado | null>(null);
  const [anulacion, setAnulacion] = useState<RemisionItem | null>(null);
  const [anulacionData, setAnulacionData] = useState<AnulacionData>({
    motivo: motivosAnulacion[0].value,
    numeroNuevaRemision: '',
    opcion: 'ANULAR_TODO',
  });
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [anulando, setAnulando] = useState(false);

  const remisionesFiltradas = useMemo(() => {
    const query = busqueda.trim().toLowerCase();
    const inicio = fechaInicio ? new Date(`${fechaInicio}T00:00:00`) : null;
    const fin = fechaFin ? new Date(`${fechaFin}T23:59:59`) : null;

    return remisiones.filter((item) => {
      const fecha = new Date(item.fechaIso);
      const matchesSearch = !query
        ? true
        : [
            item.numero,
            item.cliente,
            item.usuario,
            item.nitCc,
            item.estadoDisplay,
            item.medioPagoDisplay,
          ]
            .join(' ')
            .toLowerCase()
            .includes(query);
      const matchesInicio = inicio ? fecha >= inicio : true;
      const matchesFin = fin ? fecha <= fin : true;
      return matchesSearch && matchesInicio && matchesFin;
    });
  }, [busqueda, remisiones, fechaInicio, fechaFin]);

  useEffect(() => {
    let isActive = true;
    const cargarRemisiones = async () => {
      setCargando(true);
      setError(null);
      try {
        const response = await ventasApi.getVentas({
          tipoComprobante: 'REMISION',
          estado: estadoFiltro === 'TODAS' ? undefined : estadoFiltro,
        });
        if (!isActive) return;
        setRemisiones(response.map(mapVentaToRemisionItem));
        setSelectedIds([]);
      } catch (err) {
        if (!isActive) return;
        setRemisiones([]);
        setError(err instanceof Error ? err.message : 'Error al cargar remisiones');
      } finally {
        if (isActive) setCargando(false);
      }
    };

    cargarRemisiones();
    return () => {
      isActive = false;
    };
  }, [estadoFiltro]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const selectedRemision = remisiones.find((item) => item.id === selectedIds[0]) ?? null;

  const handleAnular = () => {
    if (!selectedRemision) return;
    setAnulacion(selectedRemision);
    setAnulacionData({
      motivo: motivosAnulacion[0].value,
      numeroNuevaRemision: '',
      opcion: 'ANULAR_TODO',
    });
  };

  const confirmarAnulacion = async () => {
    if (!anulacion) return;
    setAnulando(true);
    setError(null);
    try {
      const descripcion = anulacionData.numeroNuevaRemision
        ? `Nueva remisión: ${anulacionData.numeroNuevaRemision}`
        : 'Anulación sin remisión de reemplazo.';
      const ventaActualizada = await ventasApi.anularVenta(anulacion.id, {
        motivo: anulacionData.motivo,
        descripcion,
        devuelve_inventario: anulacionData.opcion === 'ANULAR_TODO',
      });
      setRemisiones((prev) =>
        prev.map((item) =>
          item.id === ventaActualizada.id
            ? mapVentaToRemisionItem({
                id: ventaActualizada.id,
                numero_comprobante: ventaActualizada.numero_comprobante,
                tipo_comprobante: ventaActualizada.tipo_comprobante,
                tipo_comprobante_display: ventaActualizada.tipo_comprobante_display,
                fecha: ventaActualizada.fecha,
                cliente: ventaActualizada.cliente,
                cliente_nombre: ventaActualizada.cliente_info?.nombre ?? item.cliente,
                cliente_numero_documento:
                  ventaActualizada.cliente_info?.numero_documento ?? item.nitCc,
                vendedor: ventaActualizada.vendedor,
                vendedor_nombre: ventaActualizada.vendedor_nombre,
                total: ventaActualizada.total,
                medio_pago: ventaActualizada.medio_pago,
                medio_pago_display: ventaActualizada.medio_pago_display,
                estado: ventaActualizada.estado,
                estado_display: ventaActualizada.estado_display,
              })
            : item
        )
      );
      setSelectedIds((prev) => prev.filter((id) => id !== anulacion.id));
      setAnulacion(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al anular remisión');
    } finally {
      setAnulando(false);
    }
  };

  const abrirDocumento = (tipo: DocumentoTipo) => {
    if (!selectedRemision) return;
    setDocumento({ remision: selectedRemision, tipo });
  };

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="rounded-lg bg-white p-4 shadow">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-slate-800">Lista de remisiones</h2>
            <p className="text-sm text-slate-500">
              Imprimir remisiones ordenadas por la más reciente.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600"
            >
              <FileSearch size={14} />
              Mostrar
            </button>
            <button
              type="button"
              onClick={handleAnular}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedRemision || selectedRemision?.estado === 'ANULADA' || anulando}
            >
              <Ban size={14} />
              Anular
            </button>
            <button
              type="button"
              onClick={() => abrirDocumento('POS')}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedRemision}
            >
              <Eye size={14} />
              Ver
            </button>
            <button
              type="button"
              onClick={() => abrirDocumento('POS')}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedRemision}
            >
              <Printer size={14} />
              Imprimir POS
            </button>
            <button
              type="button"
              onClick={() => abrirDocumento('CARTA')}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedRemision}
            >
              <FileText size={14} />
              Carta
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4 border-b border-slate-200 pb-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500">Estado</label>
            <select
              value={estadoFiltro}
              onChange={(event) =>
                setEstadoFiltro(event.target.value as 'CONFIRMADA' | 'ANULADA' | 'TODAS')
              }
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="CONFIRMADA">Confirmadas</option>
              <option value="ANULADA">Anuladas</option>
              <option value="TODAS">Todas</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500">Fecha inicio</label>
            <input
              type="date"
              value={fechaInicio}
              onChange={(event) => setFechaInicio(event.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500">Fecha final</label>
            <input
              type="date"
              value={fechaFin}
              onChange={(event) => setFechaFin(event.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500">Buscar por</label>
            <div className="relative">
              <input
                value={busqueda}
                onChange={(event) => setBusqueda(event.target.value)}
                placeholder="Número, cliente, usuario..."
                className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm"
              />
              <ChevronDown
                size={14}
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
            </div>
          </div>
        </div>

        <div className="mt-3 rounded border border-slate-200">
          {error && (
            <div className="border-b border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-600">
              {error}
            </div>
          )}
          <div className="bg-yellow-100 px-3 py-2 text-xs font-semibold uppercase text-slate-600">
            Seleccione las filas deseadas, o presione en la esquina superior izquierda para
            seleccionar toda la tabla. Presione Ctrl + C para pegar en Excel.
          </div>
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-yellow-200 text-xs uppercase text-slate-700">
                <tr>
                  <th className="px-2 py-2 text-left">
                    <input
                      type="checkbox"
                      checked={
                        selectedIds.length === remisionesFiltradas.length &&
                        remisionesFiltradas.length > 0
                      }
                      onChange={(event) =>
                        setSelectedIds(
                          event.target.checked ? remisionesFiltradas.map((item) => item.id) : []
                        )
                      }
                    />
                  </th>
                  <th className="px-2 py-2 text-left">Prefijo</th>
                  <th className="px-2 py-2 text-left">Remisión</th>
                  <th className="px-2 py-2 text-left">Fecha/Hora</th>
                  <th className="px-2 py-2 text-left">Estado</th>
                  <th className="px-2 py-2 text-left">Medio/Pago</th>
                  <th className="px-2 py-2 text-right">Total</th>
                  <th className="px-2 py-2 text-left">NIT/CC</th>
                  <th className="px-2 py-2 text-left">Cliente</th>
                  <th className="px-2 py-2 text-left">Usuario</th>
                </tr>
              </thead>
              <tbody>
                {cargando && (
                  <tr>
                    <td colSpan={10} className="px-4 py-6 text-center text-sm text-slate-500">
                      Cargando remisiones...
                    </td>
                  </tr>
                )}
                {!cargando &&
                  remisionesFiltradas.map((remision) => {
                    const selected = selectedIds.includes(remision.id);
                    return (
                      <tr
                        key={remision.id}
                        className={`border-t border-slate-200 ${
                          selected ? 'bg-blue-100' : 'bg-white'
                        }`}
                      >
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleSelect(remision.id)}
                          />
                        </td>
                        <td className="px-2 py-2 font-semibold text-slate-700">
                          {remision.prefijo}
                        </td>
                        <td className="px-2 py-2 text-slate-700">{remision.numero}</td>
                        <td className="px-2 py-2 text-slate-600">{remision.fechaHora}</td>
                        <td className="px-2 py-2 text-slate-600">{remision.estadoDisplay}</td>
                        <td className="px-2 py-2 text-slate-600">{remision.medioPagoDisplay}</td>
                        <td className="px-2 py-2 text-right text-rose-600">
                          {currencyFormatter.format(remision.total)}
                        </td>
                        <td className="px-2 py-2 text-slate-600">{remision.nitCc}</td>
                        <td className="px-2 py-2 text-slate-600">{remision.cliente}</td>
                        <td className="px-2 py-2 text-slate-600">{remision.usuario}</td>
                      </tr>
                    );
                  })}
                {!cargando && remisionesFiltradas.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-4 py-6 text-center text-sm text-slate-500">
                      No hay remisiones para mostrar con los filtros actuales.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        <div className="mt-2 text-xs text-slate-500">
          En el sistema hay: {remisiones.length} remisiones registradas. En la fecha seleccionada:{' '}
          {fechaInicio} - {fechaFin}. Remisionado (no incluye anuladas):{' '}
          {currencyFormatter.format(
            remisionesFiltradas.reduce(
              (acc, item) => (item.estado === 'ANULADA' ? acc : acc + item.total),
              0
            )
          )}
          .
        </div>
      </div>

      {documento && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4">
          <div className="relative w-full max-w-3xl rounded-lg bg-white p-6 shadow-xl">
            <button
              type="button"
              className="absolute right-4 top-4 text-slate-500 hover:text-slate-700"
              onClick={() => setDocumento(null)}
            >
              <X size={20} />
            </button>
            <div className="space-y-4">
              <div className="text-center">
                <p className="text-xs uppercase text-slate-500">Documento</p>
                <h3 className="text-lg font-semibold text-slate-800">
                  Remisión ({documento.tipo})
                </h3>
              </div>
              <div className="rounded border border-slate-200 p-4 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold text-slate-500">Motorepuestos Las Africanas</p>
                    <p className="text-xs text-slate-500">NIT: 91.068.915-8</p>
                    <p className="text-xs text-slate-500">
                      Calle 6 # 12A-45 Gaira, Santa Marta
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs uppercase text-slate-500">Remisión</p>
                    <p className="text-lg font-semibold text-slate-800">
                      {documento.remision.prefijo} {documento.remision.numero}
                    </p>
                    <p className="text-xs text-slate-500">{documento.remision.fechaHora}</p>
                  </div>
                </div>
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-slate-500">Cliente</p>
                    <p className="font-semibold text-slate-700">
                      {documento.remision.cliente}
                    </p>
                    <p className="text-xs text-slate-500">NIT/CC: {documento.remision.nitCc}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Medio de pago</p>
                    <p className="font-semibold text-slate-700">
                      {documento.remision.medioPagoDisplay}
                    </p>
                    <p className="text-xs text-slate-500">
                      Estado: {documento.remision.estadoDisplay}
                    </p>
                  </div>
                </div>
                <div className="mt-4 border-t border-dashed border-slate-200 pt-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Subtotal</span>
                    <span className="font-semibold text-slate-700">
                      {currencyFormatter.format(documento.remision.total * 0.88)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Impuestos</span>
                    <span className="font-semibold text-slate-700">
                      {currencyFormatter.format(documento.remision.total * 0.12)}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-base font-semibold text-slate-800">
                    <span>Total a pagar</span>
                    <span>{currencyFormatter.format(documento.remision.total)}</span>
                  </div>
                </div>
                <div className="mt-4 rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">
                  {documento.tipo === 'POS'
                    ? 'Documento POS para impresión rápida.'
                    : 'Documento carta para archivo y entrega al cliente.'}
                </div>
              </div>
              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setDocumento(null)}
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
                >
                  <Printer size={16} />
                  Imprimir
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {anulacion && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4">
          <div className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <button
              type="button"
              className="absolute right-4 top-4 text-slate-500 hover:text-slate-700"
              onClick={() => setAnulacion(null)}
            >
              <X size={20} />
            </button>
            <div className="text-center">
              <p className="text-xs uppercase text-slate-500">Anular remisión</p>
              <h3 className="text-xl font-semibold text-slate-800">
                {anulacion.prefijo} {anulacion.numero}
              </h3>
              <p className="text-base text-slate-600">
                {currencyFormatter.format(anulacion.total)}
              </p>
            </div>
            <div className="mt-4 space-y-4">
              <div>
                <label className="text-xs font-semibold uppercase text-slate-500">
                  Motivo / causa
                </label>
                <select
                  value={anulacionData.motivo}
                  onChange={(event) =>
                    setAnulacionData((prev) => ({ ...prev, motivo: event.target.value }))
                  }
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-2 text-sm"
                >
                  {motivosAnulacion.map((motivo) => (
                    <option key={motivo.value} value={motivo.value}>
                      {motivo.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="rounded border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-600">
                Escriba el número de la nueva remisión que reemplaza esta.
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500">
                  No. remisión nueva (si aplica)
                </label>
                <input
                  value={anulacionData.numeroNuevaRemision}
                  onChange={(event) =>
                    setAnulacionData((prev) => ({
                      ...prev,
                      numeroNuevaRemision: event.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-2 text-sm"
                  placeholder="Prefijo y número"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="radio"
                    name="tipo-anulacion-remision"
                    checked={anulacionData.opcion === 'ANULAR_TODO'}
                    onChange={() =>
                      setAnulacionData((prev) => ({ ...prev, opcion: 'ANULAR_TODO' }))
                    }
                  />
                  Anular todo
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="radio"
                    name="tipo-anulacion-remision"
                    checked={anulacionData.opcion === 'USAR_DATOS'}
                    onChange={() =>
                      setAnulacionData((prev) => ({ ...prev, opcion: 'USAR_DATOS' }))
                    }
                  />
                  Usar datos en otra remisión
                </label>
              </div>
            </div>
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={confirmarAnulacion}
                className="rounded bg-slate-200 px-6 py-2 text-sm font-semibold uppercase text-slate-700 disabled:opacity-50"
                disabled={anulando}
              >
                {anulando ? 'Anulando...' : 'Anular'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
