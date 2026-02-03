import { useEffect, useMemo, useState } from 'react';
import { FileSearch, Printer, Ban, Eye, X, ChevronDown, FileText } from 'lucide-react';
import { configuracionAPI } from '../api/configuracion';
import { ventasApi, type Venta, type VentaListItem } from '../api/ventas';
import ComprobanteTemplate from '../components/ComprobanteTemplate';
import type { ConfiguracionEmpresa, ConfiguracionFacturacion } from '../types';
import { printComprobante } from '../utils/printComprobante';

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
  maximumFractionDigits: 0,
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
  const fechaBase = venta.facturada_at ?? venta.fecha;
  const { prefijo, numero } = splitNumeroComprobante(venta.numero_comprobante);
  return {
    id: venta.id,
    prefijo,
    numero,
    fechaHora: formatFechaHora(fechaBase),
    fechaIso: fechaBase,
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
  const today = new Date().toISOString().split('T')[0];
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [remisiones, setRemisiones] = useState<RemisionItem[]>([]);
  const [busqueda, setBusqueda] = useState('');
  const [estadoFiltro, setEstadoFiltro] = useState<'FACTURADA' | 'ANULADA' | 'TODAS'>(
    'FACTURADA'
  );
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [documento, setDocumento] = useState<DocumentoSeleccionado | null>(null);
  const [detalleRemision, setDetalleRemision] = useState<Venta | null>(null);
  const [detalleCargando, setDetalleCargando] = useState(false);
  const [detalleError, setDetalleError] = useState<string | null>(null);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa | null>(null);
  const [facturacion, setFacturacion] = useState<ConfiguracionFacturacion | null>(null);
  const [anulacion, setAnulacion] = useState<RemisionItem | null>(null);
  const [anulacionData, setAnulacionData] = useState<AnulacionData>({
    motivo: motivosAnulacion[0].value,
    numeroNuevaRemision: '',
  });
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [anulando, setAnulando] = useState(false);

  const cargarRemisiones = async (filters: {
    estado: 'FACTURADA' | 'ANULADA' | 'TODAS';
    fechaInicio?: string;
    fechaFin?: string;
    search?: string;
  }) => {
    setCargando(true);
    setError(null);
    try {
      const search = filters.search?.trim();
      const response = await ventasApi.getVentas({
        tipoComprobante: 'REMISION',
        estado: filters.estado === 'TODAS' ? undefined : filters.estado,
        fechaInicio: filters.fechaInicio || undefined,
        fechaFin: filters.fechaFin || undefined,
        search: search ? search : undefined,
      });
      setRemisiones(response.map(mapVentaToRemisionItem));
      setSelectedIds([]);
    } catch (err) {
      setRemisiones([]);
      setError(err instanceof Error ? err.message : 'Error al cargar remisiones');
    } finally {
      setCargando(false);
    }
  };

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
    cargarRemisiones({
      estado: estadoFiltro,
      fechaInicio,
      fechaFin,
    });
  }, [estadoFiltro, fechaInicio, fechaFin]);

  useEffect(() => {
    configuracionAPI
      .obtenerEmpresa()
      .then(setEmpresa)
      .catch(() => setEmpresa(null));
    configuracionAPI
      .obtenerFacturacion()
      .then(setFacturacion)
      .catch(() => setFacturacion(null));
  }, []);

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
      await ventasApi.anularVenta(anulacion.id, {
        motivo: anulacionData.motivo,
        descripcion,
        devuelve_inventario: true,
      });
      await cargarRemisiones({
        estado: estadoFiltro,
        fechaInicio,
        fechaFin,
        search: busqueda,
      });
      setAnulacion(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al anular remisión');
    } finally {
      setAnulando(false);
    }
  };

  const abrirDocumento = async (tipo: DocumentoTipo) => {
    if (!selectedRemision) return;
    setDocumento({ remision: selectedRemision, tipo });
    setDetalleCargando(true);
    setDetalleError(null);
    try {
      const detalle = await ventasApi.getVenta(selectedRemision.id);
      setDetalleRemision(detalle);
    } catch (err) {
      setDetalleRemision(null);
      setDetalleError(err instanceof Error ? err.message : 'No se pudo cargar el detalle.');
    } finally {
      setDetalleCargando(false);
    }
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
              onClick={() =>
                cargarRemisiones({
                  estado: estadoFiltro,
                  fechaInicio,
                  fechaFin,
                  search: busqueda,
                })
              }
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600"
              disabled={cargando}
            >
              <FileSearch size={14} />
              Actualizar
            </button>
            <button
              type="button"
              onClick={() => {
                setEstadoFiltro('ANULADA');
                cargarRemisiones({
                  estado: 'ANULADA',
                  fechaInicio,
                  fechaFin,
                  search: busqueda,
                });
              }}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600"
              disabled={cargando}
            >
              <FileSearch size={14} />
              Ver anuladas
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
              Imprimir Carta
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4 border-b border-slate-200 pb-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500">Estado</label>
            <select
              value={estadoFiltro}
              onChange={(event) =>
                setEstadoFiltro(event.target.value as 'FACTURADA' | 'ANULADA' | 'TODAS')
              }
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="FACTURADA">Confirmadas</option>
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
          <div className="relative w-full max-w-5xl rounded-lg bg-white p-6 shadow-xl">
            <button
              type="button"
              className="absolute right-4 top-4 text-slate-500 hover:text-slate-700"
              onClick={() => {
                setDocumento(null);
                setDetalleRemision(null);
                setDetalleError(null);
              }}
            >
              <X size={20} />
            </button>
            <div className="space-y-4">
              <div className="text-center">
                <p className="text-xs uppercase text-slate-500">Documento</p>
                <h3 className="text-lg font-semibold text-slate-800">Remisión ({documento.tipo})</h3>
              </div>
              <div className="max-h-[70vh] overflow-auto rounded border border-slate-200 bg-slate-50 p-4">
                {detalleCargando ? (
                  <p className="text-center text-sm text-slate-500">
                    Cargando detalle de la remisión...
                  </p>
                ) : null}
                {detalleError ? (
                  <p className="text-center text-sm text-rose-600">{detalleError}</p>
                ) : null}
                <ComprobanteTemplate
                  formato={documento.tipo}
                  tipo="REMISION"
                  numero={`${documento.remision.prefijo} ${documento.remision.numero}`}
                  fecha={detalleRemision?.fecha ?? documento.remision.fechaIso}
                  clienteNombre={detalleRemision?.cliente_info?.nombre ?? documento.remision.cliente}
                  clienteDocumento={
                    detalleRemision?.cliente_info?.numero_documento ?? documento.remision.nitCc
                  }
                  medioPago={detalleRemision?.medio_pago_display ?? documento.remision.medioPagoDisplay}
                  estado={detalleRemision?.estado_display ?? documento.remision.estadoDisplay}
                  detalles={
                    detalleRemision?.detalles?.map((detalle) => ({
                      descripcion: detalle.producto_nombre ?? 'Producto',
                      codigo: detalle.producto_codigo ?? '',
                      cantidad: Number(detalle.cantidad),
                      precioUnitario: Number(detalle.precio_unitario),
                      descuento: Number(detalle.descuento_unitario),
                      ivaPorcentaje: Number(detalle.iva_porcentaje),
                      total: Number(detalle.total),
                    })) ?? []
                  }
                  subtotal={detalleRemision ? Number(detalleRemision.subtotal) : documento.remision.total}
                  descuento={detalleRemision ? Number(detalleRemision.descuento_valor) : 0}
                  iva={detalleRemision ? Number(detalleRemision.iva) : 0}
                  total={detalleRemision ? Number(detalleRemision.total) : documento.remision.total}
                  efectivoRecibido={
                    detalleRemision?.efectivo_recibido !== undefined &&
                    detalleRemision?.efectivo_recibido !== null
                      ? Number(detalleRemision.efectivo_recibido)
                      : undefined
                  }
                  cambio={
                    detalleRemision?.cambio !== undefined && detalleRemision?.cambio !== null
                      ? Number(detalleRemision.cambio)
                      : undefined
                  }
                  notas={facturacion?.notas_factura}
                  resolucion={facturacion?.resolucion}
                  empresa={empresa}
                />
              </div>
              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setDocumento(null);
                    setDetalleRemision(null);
                    setDetalleError(null);
                  }}
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (!documento) return;
                    const detalle = detalleRemision;
                    const detalles = detalle?.detalles?.map((item) => ({
                      descripcion: item.producto_nombre ?? 'Producto',
                      codigo: item.producto_codigo ?? '',
                      cantidad: Number(item.cantidad),
                      precioUnitario: Number(item.precio_unitario),
                      descuento: Number(item.descuento_unitario),
                      ivaPorcentaje: Number(item.iva_porcentaje),
                      total: Number(item.total),
                    }));
                    printComprobante({
                      formato: documento.tipo,
                      tipo: 'REMISION',
                      numero: `${documento.remision.prefijo} ${documento.remision.numero}`,
                      fecha: detalle?.fecha ?? documento.remision.fechaIso,
                      clienteNombre: detalle?.cliente_info?.nombre ?? documento.remision.cliente,
                      clienteDocumento:
                        detalle?.cliente_info?.numero_documento ?? documento.remision.nitCc,
                      medioPago:
                        detalle?.medio_pago_display ?? documento.remision.medioPagoDisplay,
                      estado: detalle?.estado_display ?? documento.remision.estadoDisplay,
                      detalles: detalles ?? [],
                      subtotal: detalle ? Number(detalle.subtotal) : documento.remision.total,
                      descuento: detalle ? Number(detalle.descuento_valor) : 0,
                      iva: detalle ? Number(detalle.iva) : 0,
                      total: detalle ? Number(detalle.total) : documento.remision.total,
                      efectivoRecibido:
                        detalle?.efectivo_recibido !== undefined &&
                        detalle?.efectivo_recibido !== null
                          ? Number(detalle.efectivo_recibido)
                          : undefined,
                      cambio:
                        detalle?.cambio !== undefined && detalle?.cambio !== null
                          ? Number(detalle.cambio)
                          : undefined,
                      notas: facturacion?.notas_factura,
                      resolucion: facturacion?.resolucion,
                      empresa,
                    });
                  }}
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
