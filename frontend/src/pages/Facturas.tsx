import { useEffect, useMemo, useRef, useState } from 'react';
import { FileSearch, Printer, Ban, Eye, X, ChevronDown, FileText } from 'lucide-react';
import { configuracionAPI } from '../api/configuracion';
import { ventasApi, type Venta, type VentaListItem } from '../api/ventas';
import { facturacionApi, resolveEstadoFactura, type FacturaElectronica } from '../modules/facturacionElectronica/services/facturacionApi';
import { useNotification } from '../contexts/NotificationContext';
import ComprobanteTemplate from '../components/ComprobanteTemplate';
import type { ConfiguracionEmpresa, ConfiguracionFacturacion } from '../types';
import { printComprobante } from '../utils/printComprobante';
import { getLocalDateInputValue } from '../utils/date';

type DocumentoTipo = 'POS' | 'CARTA';

type FacturaItem = {
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
  electronica?: FacturaElectronica;
};

type DocumentoSeleccionado = {
  factura: FacturaItem;
  tipo: DocumentoTipo;
};

type AnulacionData = {
  motivo: string;
  numeroNuevaFactura: string;
  devuelveInventario: boolean;
};

const motivosAnulacion = [
  { value: 'DEVOLUCION_PARCIAL', label: 'Devolución parcial' },
  { value: 'DEVOLUCION_TOTAL', label: 'Devolución total' },
  { value: 'ERROR_PRECIOS', label: 'Error con precios en la factura' },
  { value: 'ERROR_CONCEPTO', label: 'Error por conceptos en la factura' },
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
    const compact = numeroComprobante.trim();
    const match = compact.match(/^([A-Za-z]+)(\d+)$/);
    if (match) {
      return { prefijo: match[1], numero: match[2] };
    }
    return { prefijo: compact.slice(0, 3), numero: compact };
  }
  return { prefijo, numero: rest.join('-') };
};

const mapVentaToFacturaItem = (venta: VentaListItem): FacturaItem => {
  const fechaBase = venta.facturada_at ?? venta.fecha;
  const numeroComprobante = venta.numero_comprobante ?? '';
  const { prefijo, numero } = splitNumeroComprobante(numeroComprobante);
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

const mapEstadoElectronicoLabel = (factura?: FacturaElectronica): string => {
  if (!factura) return 'Sin emisión';
  const estado = resolveEstadoFactura(factura);
  if (estado === 'ACEPTADA') return 'Aceptada';
  if (estado === 'ACEPTADA_CON_OBSERVACIONES') return 'Aceptada con observaciones';
  if (estado === 'RECHAZADA') return 'Rechazada';
  if (estado === 'ERROR_INTEGRACION') return 'Error integración';
  if (estado === 'ERROR_PERSISTENCIA') return 'Error persistencia';
  if (estado === 'PENDIENTE_REINTENTO') return 'Pendiente reintento';
  return 'Sin emisión';
};

const hasValidElectronicDocument = (factura?: FacturaElectronica): boolean => {
  if (!factura) return false;
  const estado = resolveEstadoFactura(factura);
  return (estado === 'ACEPTADA' || estado === 'ACEPTADA_CON_OBSERVACIONES') && Boolean(factura.numero && factura.cufe);
};

const resolveFacturaPublicUrl = (factura?: FacturaElectronica): string => {
  if (!factura) return '';
  if (factura.factus_public_url && factura.factus_public_url.trim()) return factura.factus_public_url;
  return factura.public_url?.trim() || '';
};

export default function Facturas() {
  const { showNotification } = useNotification();
  const today = getLocalDateInputValue();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [facturas, setFacturas] = useState<FacturaItem[]>([]);
  const [busqueda, setBusqueda] = useState('');
  const [estadoFiltro, setEstadoFiltro] = useState<'FACTURADA' | 'ANULADA' | 'TODAS'>(
    'TODAS'
  );
  const [estadoElectronicoFiltro, setEstadoElectronicoFiltro] = useState<string>('TODAS');
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [documento, setDocumento] = useState<DocumentoSeleccionado | null>(null);
  const [detalleFactura, setDetalleFactura] = useState<Venta | null>(null);
  const [detalleCargando, setDetalleCargando] = useState(false);
  const [detalleError, setDetalleError] = useState<string | null>(null);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa | null>(null);
  const [facturacion, setFacturacion] = useState<ConfiguracionFacturacion | null>(null);
  const [anulacion, setAnulacion] = useState<FacturaItem | null>(null);
  const [anulacionData, setAnulacionData] = useState<AnulacionData>({
    motivo: motivosAnulacion[0].value,
    numeroNuevaFactura: '',
    devuelveInventario: true,
  });
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [anulando, setAnulando] = useState(false);
  const [accionesElectronicas, setAccionesElectronicas] = useState<Record<string, string | null>>({});
  const ventasAbortRef = useRef<AbortController | null>(null);

  const cargarFacturas = async (filters: {
    estado: 'FACTURADA' | 'ANULADA' | 'TODAS';
    fechaInicio?: string;
    fechaFin?: string;
    search?: string;
  }) => {
    setCargando(true);
    setError(null);
    try {
      const search = filters.search?.trim();
      ventasAbortRef.current?.abort();
      const controller = new AbortController();
      ventasAbortRef.current = controller;
      const response = await ventasApi.getVentas({
        tipoComprobante: 'FACTURA',
        estado: filters.estado === 'TODAS' ? undefined : filters.estado,
        fechaInicio: filters.fechaInicio || undefined,
        fechaFin: filters.fechaFin || undefined,
        search: search ? search : undefined,
      }, { signal: controller.signal });
      let facturasElectronicas: FacturaElectronica[] = [];
      try {
        facturasElectronicas = await facturacionApi.getFacturas();
      } catch (facturaError) {
        console.error('No fue posible cargar el estado electrónico de facturas', facturaError);
      }
      const porVentaId = new Map(
        facturasElectronicas
          .filter((item) => typeof item.venta_id === 'number')
          .map((item) => [item.venta_id as number, item])
      );
      const porNumero = new Map(
        facturasElectronicas.flatMap((item) => {
          const keys = [
            String(item.numero ?? '').trim(),
            String(item.reference_code ?? '').trim(),
          ].filter((value) => value.length > 0);
          return keys.map((key) => [key, item] as const);
        })
      );
      setFacturas(
        response.map((venta) => {
          const mapped = mapVentaToFacturaItem(venta);
          const numeroCompleto = venta.numero_comprobante ?? '';
          return {
            ...mapped,
            electronica:
              (venta.factura_electronica as FacturaElectronica | null | undefined) ??
              porVentaId.get(venta.id) ??
              porNumero.get(numeroCompleto) ??
              porNumero.get(mapped.numero) ??
              undefined,
          };
        })
      );
      setSelectedIds([]);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      console.error('Error cargando listado de facturas', err);
      setFacturas([]);
      setError(err instanceof Error ? err.message : 'Error al cargar facturas');
    } finally {
      setCargando(false);
    }
  };

  const facturasFiltradas = useMemo(() => {
    const query = busqueda.trim().toLowerCase();
    const inicio = fechaInicio ? new Date(`${fechaInicio}T00:00:00`) : null;
    const fin = fechaFin ? new Date(`${fechaFin}T23:59:59`) : null;

    return facturas.filter((item) => {
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
      const estadoElectronico = item.electronica ? resolveEstadoFactura(item.electronica) : 'SIN_EMISION';
      const matchesEstadoElectronico =
        estadoElectronicoFiltro === 'TODAS' ? true : estadoElectronico === estadoElectronicoFiltro;
      return matchesSearch && matchesInicio && matchesFin && matchesEstadoElectronico;
    });
  }, [busqueda, facturas, fechaInicio, fechaFin, estadoElectronicoFiltro]);

  useEffect(() => {
    cargarFacturas({
      estado: estadoFiltro,
      fechaInicio,
      fechaFin,
    });
    return () => {
      ventasAbortRef.current?.abort();
    };
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

  const selectedFactura = facturas.find((item) => item.id === selectedIds[0]) ?? null;
  const anulacionRequiereNotaCredito = Boolean(
    anulacion &&
      (anulacion.electronica?.estado_dian ||
        anulacion.electronica?.estado ||
        anulacion.electronica?.status) === 'ACEPTADA'
  );

  const handleAccionElectronica = async (
    factura: FacturaItem,
    action: 'estado' | 'xml' | 'pdf' | 'correo'
  ) => {
    const numero = factura.electronica?.numero;
    const facturaId = factura.electronica?.id;
    if (!hasValidElectronicDocument(factura.electronica)) {
      showNotification({
        type: 'error',
        message: 'La factura electrónica aún no está validada. Esta acción solo está disponible en estado Aceptada.',
      });
      return;
    }
    if (!numero || !facturaId) {
      showNotification({
        type: 'error',
        message: 'Esta factura no tiene emisión electrónica registrada.',
      });
      return;
    }
    setAccionesElectronicas((prev) => ({ ...prev, [numero]: action }));
    try {
      if (action === 'estado') {
        const data = await facturacionApi.getEstadoFactura(numero);
        showNotification({
          type: 'success',
          message: `Estado DIAN (${numero}): ${resolveEstadoFactura(data)}`,
        });
      } else if (action === 'xml') {
        await facturacionApi.descargarXMLById(facturaId, numero);
      } else if (action === 'pdf') {
        await facturacionApi.descargarPDFById(facturaId, numero);
      } else {
        await facturacionApi.enviarFacturaCorreoById(facturaId);
        showNotification({
          type: 'success',
          message: `Factura ${numero} enviada por correo.`,
        });
      }
    } catch (error) {
      showNotification({
        type: 'error',
        message: error instanceof Error ? error.message : 'No se pudo ejecutar la acción electrónica.',
      });
    } finally {
      setAccionesElectronicas((prev) => ({ ...prev, [numero]: null }));
    }
  };

  const handleAnular = () => {
    if (!selectedFactura) return;
    setAnulacion(selectedFactura);
    setAnulacionData({
      motivo: motivosAnulacion[0].value,
      numeroNuevaFactura: '',
      devuelveInventario: true,
    });
  };

  const confirmarAnulacion = async () => {
    if (!anulacion) return;
    setAnulando(true);
    setError(null);
    try {
      const descripcion = anulacionData.numeroNuevaFactura
        ? `Nueva factura: ${anulacionData.numeroNuevaFactura}`
        : 'Anulación sin factura de reemplazo.';
      const ventaAnulada = await ventasApi.anularVenta(anulacion.id, {
        motivo: anulacionData.motivo,
        descripcion,
        devuelve_inventario: anulacionData.devuelveInventario,
      });
      const numeroNotaCredito = ventaAnulada?.nota_credito_emitida?.number;
      const anulacionPendiente = ventaAnulada?.finalized === false || ventaAnulada?.result === 'pending_dian';
      showNotification({
        type: anulacionPendiente ? 'warning' : 'success',
        message: anulacionPendiente
          ? `Nota crédito ${numeroNotaCredito || ''} creada y pendiente DIAN. La venta aún no queda anulada.`
          : (numeroNotaCredito
              ? `Factura anulada. Nota crédito emitida: ${numeroNotaCredito}.`
              : 'Factura anulada correctamente.'),
      });
      await cargarFacturas({
        estado: estadoFiltro,
        fechaInicio,
        fechaFin,
        search: busqueda,
      });
      setAnulacion(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al anular factura');
    } finally {
      setAnulando(false);
    }
  };

  const abrirDocumento = async (tipo: DocumentoTipo) => {
    if (!selectedFactura) return;
    setDocumento({ factura: selectedFactura, tipo });
    setDetalleCargando(true);
    setDetalleError(null);
    try {
      const detalle = await ventasApi.getVenta(selectedFactura.id);
      setDetalleFactura(detalle);
    } catch (err) {
      setDetalleFactura(null);
      setDetalleError(err instanceof Error ? err.message : 'No se pudo cargar el detalle.');
    } finally {
      setDetalleCargando(false);
    }
  };

  return (
    <div className="space-y-4 px-3 py-4 sm:px-6 sm:py-6">
      <div className="rounded-lg bg-white p-4 shadow">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-slate-800">Lista de facturas</h2>
            <p className="text-sm text-slate-500">
              Imprimir facturas ordenadas por la más reciente.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() =>
                cargarFacturas({
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
              disabled={!selectedFactura || selectedFactura?.estado === 'ANULADA' || anulando}
            >
              <Ban size={14} />
              Anular
            </button>
            <button
              type="button"
              onClick={() => abrirDocumento('POS')}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedFactura}
            >
              <Eye size={14} />
              Ver
            </button>
            <button
              type="button"
              onClick={() => abrirDocumento('POS')}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedFactura}
            >
              <Printer size={14} />
              Imprimir POS
            </button>
            <button
              type="button"
              onClick={() => abrirDocumento('CARTA')}
              className="flex items-center gap-2 rounded border border-slate-300 px-3 py-1.5 text-xs font-semibold uppercase text-slate-600 disabled:opacity-50"
              disabled={!selectedFactura}
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
              <option value="FACTURADA">Facturadas</option>
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
            <label className="text-xs font-semibold text-slate-500">Estado electrónico</label>
            <select
              value={estadoElectronicoFiltro}
              onChange={(event) => setEstadoElectronicoFiltro(event.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="TODAS">Todos</option>
              <option value="RECHAZADA">Rechazadas</option>
              <option value="PENDIENTE_REINTENTO">Pendientes reintento</option>
              <option value="ERROR_INTEGRACION">Error integración</option>
              <option value="ERROR_PERSISTENCIA">Error persistencia</option>
              <option value="ACEPTADA_CON_OBSERVACIONES">Aceptadas con observaciones</option>
              <option value="ACEPTADA">Aceptadas</option>
            </select>
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

        <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          {error && (
            <div className="border-b border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-600">
              {error}
            </div>
          )}
          <div className="overflow-auto">
            <table className="w-full min-w-[1460px] table-fixed text-sm">
              <thead className="bg-sky-100 text-[11px] uppercase tracking-wide text-slate-700">
                <tr>
                  <th className="w-10 px-2 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === facturasFiltradas.length && facturasFiltradas.length > 0}
                      onChange={(event) =>
                        setSelectedIds(
                          event.target.checked ? facturasFiltradas.map((item) => item.id) : []
                        )
                      }
                    />
                  </th>
                  <th className="w-20 px-2 py-2 text-left">Prefijo</th>
                  <th className="w-20 px-2 py-2 text-left">Factura</th>
                  <th className="w-36 px-2 py-2 text-left">Fecha/Hora</th>
                  <th className="w-24 px-2 py-2 text-left">Estado</th>
                  <th className="w-28 px-2 py-2 text-left">Electrónica</th>
                  <th className="w-28 px-2 py-2 text-left">Medio/Pago</th>
                  <th className="w-28 px-2 py-2 text-right">Total</th>
                  <th className="w-28 px-2 py-2 text-left">NIT/CC</th>
                  <th className="w-44 px-2 py-2 text-left">Cliente</th>
                  <th className="w-32 px-2 py-2 text-left">Usuario</th>
                  <th className="w-[20rem] px-2 py-2 text-left">CUFE / Ref</th>
                  <th className="w-24 px-2 py-2 text-left">XML</th>
                  <th className="w-24 px-2 py-2 text-left">PDF</th>
                  <th className="w-24 px-2 py-2 text-left">Correo</th>
                  <th className="w-44 px-2 py-2 text-left">Acciones FE</th>
                </tr>
              </thead>
              <tbody>
                {cargando && (
                  <tr>
                    <td colSpan={16} className="px-4 py-6 text-center text-sm text-slate-500">
                      Cargando facturas...
                    </td>
                  </tr>
                )}
                {!cargando &&
                  facturasFiltradas.map((factura) => {
                    const selected = selectedIds.includes(factura.id);
                    const electronicaValida =
                      factura.electronica && hasValidElectronicDocument(factura.electronica)
                        ? factura.electronica
                        : null;
                    const publicUrl = resolveFacturaPublicUrl(electronicaValida ?? undefined);
                    return (
                      <tr
                        key={factura.id}
                        className={`border-t border-slate-100 align-top ${
                          selected ? 'bg-blue-50' : 'bg-white'
                        }`}
                      >
                        <td className="px-2 py-2.5">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleSelect(factura.id)}
                          />
                        </td>
                        <td className="px-2 py-2.5 font-semibold text-slate-700">
                          {factura.prefijo}
                        </td>
                        <td className="px-2 py-2.5 text-slate-700">{factura.numero}</td>
                        <td className="px-2 py-2.5 text-slate-600">{factura.fechaHora}</td>
                        <td className="px-2 py-2.5 text-slate-600">{factura.estadoDisplay}</td>
                        <td className="px-2 py-2.5 text-slate-600">
                          {mapEstadoElectronicoLabel(factura.electronica)}
                        </td>
                        <td className="px-2 py-2.5 text-slate-600">{factura.medioPagoDisplay}</td>
                        <td className="px-2 py-2.5 text-right text-rose-600">
                          {currencyFormatter.format(factura.total)}
                        </td>
                        <td className="px-2 py-2.5 text-slate-600">{factura.nitCc}</td>
                        <td className="px-2 py-2.5 text-slate-600">{factura.cliente}</td>
                        <td className="px-2 py-2.5 text-slate-600">{factura.usuario}</td>
                        <td className="px-2 py-2.5 text-[11px] text-slate-600">
                          {electronicaValida ? (
                            <div className="max-w-[20rem] space-y-1 whitespace-normal break-words [overflow-wrap:anywhere]">
                              <p className="leading-tight">
                                <span className="font-semibold text-slate-700">CUFE:</span>{' '}
                                {electronicaValida.cufe ?? 'N/D'}
                              </p>
                              <p className="leading-tight">
                                <span className="font-semibold text-slate-700">FE:</span>{' '}
                                {electronicaValida.numero}
                              </p>
                              <p className="leading-tight">
                                <span className="font-semibold text-slate-700">Ref local:</span>{' '}
                                {electronicaValida.reference_code ?? factura.numero}
                              </p>
                              {electronicaValida.observaciones ? (
                                <p className="leading-tight text-amber-700">
                                  Obs: {electronicaValida.observaciones}
                                </p>
                              ) : null}
                              {publicUrl ? (
                                <a
                                  href={publicUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-block break-all text-blue-600 underline"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  Ver en DIAN/Factus
                                </a>
                              ) : null}
                            </div>
                          ) : (
                            'Sin emisión FE'
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-xs text-slate-600">
                          {factura.electronica?.xml_local_path ? 'Sí' : 'No'}
                        </td>
                        <td className="px-2 py-2.5 text-xs text-slate-600">
                          {factura.electronica?.pdf_local_path ? 'Sí' : 'No'}
                        </td>
                        <td className="px-2 py-2.5 text-xs text-slate-600">
                          {factura.electronica?.correo_enviado ? 'Enviado' : 'Pendiente'}
                        </td>
                        <td className="px-2 py-2.5">
                          {electronicaValida ? (
                            <div className="flex flex-wrap gap-1">
                              <button
                                type="button"
                                className="rounded bg-blue-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[electronicaValida.numero])}
                                onClick={() => handleAccionElectronica(factura, 'estado')}
                              >
                                Estado
                              </button>
                              <button
                                type="button"
                                className="rounded bg-indigo-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[electronicaValida.numero])}
                                onClick={() => handleAccionElectronica(factura, 'xml')}
                              >
                                XML
                              </button>
                              <button
                                type="button"
                                className="rounded bg-violet-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[electronicaValida.numero])}
                                onClick={() => handleAccionElectronica(factura, 'pdf')}
                              >
                                PDF
                              </button>
                              <button
                                type="button"
                                className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[electronicaValida.numero])}
                                onClick={() => handleAccionElectronica(factura, 'correo')}
                              >
                                Correo
                              </button>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">N/A</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                {!cargando && facturasFiltradas.length === 0 && (
                  <tr>
                    <td colSpan={16} className="px-4 py-6 text-center text-sm text-slate-500">
                      No hay facturas para mostrar con los filtros actuales.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        <div className="mt-2 text-xs text-slate-500">
          En el sistema hay: {facturas.length} facturas registradas. En la fecha seleccionada:{' '}
          {fechaInicio} - {fechaFin}. Facturado (no incluye anuladas):{' '}
          {currencyFormatter.format(
            facturasFiltradas.reduce(
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
                setDetalleFactura(null);
                setDetalleError(null);
              }}
            >
              <X size={20} />
            </button>
            <div className="space-y-4">
              <div className="text-center">
                <p className="text-xs uppercase text-slate-500">Documento</p>
                <h3 className="text-lg font-semibold text-slate-800">
                  Factura de venta ({documento.tipo})
                </h3>
              </div>
              <div className="max-h-[70vh] overflow-auto rounded border border-slate-200 bg-slate-50 p-4">
                {detalleCargando ? (
                  <p className="text-center text-sm text-slate-500">
                    Cargando detalle de la factura...
                  </p>
                ) : null}
                {detalleError ? (
                  <p className="text-center text-sm text-rose-600">{detalleError}</p>
                ) : null}
                <ComprobanteTemplate
                  formato={documento.tipo}
                  tipo="FACTURA"
                  numero={`${documento.factura.prefijo} ${documento.factura.numero}`}
                  fecha={detalleFactura?.fecha ?? documento.factura.fechaIso}
                  clienteNombre={detalleFactura?.cliente_info?.nombre ?? documento.factura.cliente}
                  clienteDocumento={
                    detalleFactura?.cliente_info?.numero_documento ?? documento.factura.nitCc
                  }
                  medioPago={detalleFactura?.medio_pago_display ?? documento.factura.medioPagoDisplay}
                  estado={detalleFactura?.estado_display ?? documento.factura.estadoDisplay}
                  detalles={
                    detalleFactura?.detalles?.map((detalle) => ({
                      descripcion: detalle.producto_nombre ?? 'Producto',
                      codigo: detalle.producto_codigo ?? '',
                      cantidad: Number(detalle.cantidad),
                      precioUnitario: Number(detalle.precio_unitario),
                      descuento: Number(detalle.descuento_unitario),
                      subtotal: Number(detalle.subtotal),
                      ivaPorcentaje: Number(detalle.iva_porcentaje),
                      ivaValor: Number(detalle.total) - Number(detalle.subtotal),
                      total: Number(detalle.total),
                    })) ?? []
                  }
                  subtotal={detalleFactura ? Number(detalleFactura.subtotal) : documento.factura.total}
                  descuento={detalleFactura ? Number(detalleFactura.descuento_valor) : 0}
                  iva={detalleFactura ? Number(detalleFactura.iva) : 0}
                  total={detalleFactura ? Number(detalleFactura.total) : documento.factura.total}
                  efectivoRecibido={
                    detalleFactura?.efectivo_recibido !== undefined &&
                    detalleFactura?.efectivo_recibido !== null
                      ? Number(detalleFactura.efectivo_recibido)
                      : undefined
                  }
                  cambio={
                    detalleFactura?.cambio !== undefined && detalleFactura?.cambio !== null
                      ? Number(detalleFactura.cambio)
                      : undefined
                  }
                  notas={facturacion?.notas_factura}
                  resolucion={facturacion?.resolucion}
                  empresa={empresa}
                  cufe={documento.factura.electronica?.cufe}
                  qrUrl={documento.factura.electronica?.public_url || documento.factura.electronica?.qr_factus}
                  qrImageUrl={documento.factura.electronica?.qr_image}
                  referenceCode={documento.factura.electronica?.reference_code}
                />
              </div>
              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setDocumento(null);
                    setDetalleFactura(null);
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
                    const detalle = detalleFactura;
                    const detalles = detalle?.detalles?.map((item) => ({
                      descripcion: item.producto_nombre ?? 'Producto',
                      codigo: item.producto_codigo ?? '',
                      cantidad: Number(item.cantidad),
                      precioUnitario: Number(item.precio_unitario),
                      descuento: Number(item.descuento_unitario),
                      subtotal: Number(item.subtotal),
                      ivaPorcentaje: Number(item.iva_porcentaje),
                      ivaValor: Number(item.total) - Number(item.subtotal),
                      total: Number(item.total),
                    }));
                    printComprobante({
                      formato: documento.tipo,
                      tipo: 'FACTURA',
                      numero: `${documento.factura.prefijo} ${documento.factura.numero}`,
                      fecha: detalle?.fecha ?? documento.factura.fechaIso,
                      clienteNombre: detalle?.cliente_info?.nombre ?? documento.factura.cliente,
                      clienteDocumento:
                        detalle?.cliente_info?.numero_documento ?? documento.factura.nitCc,
                      medioPago: detalle?.medio_pago_display ?? documento.factura.medioPagoDisplay,
                      estado: detalle?.estado_display ?? documento.factura.estadoDisplay,
                      detalles: detalles ?? [],
                      subtotal: detalle ? Number(detalle.subtotal) : documento.factura.total,
                      descuento: detalle ? Number(detalle.descuento_valor) : 0,
                      iva: detalle ? Number(detalle.iva) : 0,
                      total: detalle ? Number(detalle.total) : documento.factura.total,
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
                      cufe: documento.factura.electronica?.cufe,
                      qrUrl:
                        documento.factura.electronica?.public_url ||
                        documento.factura.electronica?.qr_factus,
                      qrImageUrl: documento.factura.electronica?.qr_image,
                      referenceCode: documento.factura.electronica?.reference_code,
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
              <p className="text-xs uppercase text-slate-500">Anular factura</p>
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
                Escriba el número de la nueva factura que reemplaza esta.
              </div>
              <div className="rounded border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700">
                Recuerde generar la nota crédito física que anula el total de la venta y
                conservar la factura marcada como ANULADA para trazabilidad contable.
              </div>
              {anulacionRequiereNotaCredito && (
                <div className="rounded border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  Se emitirá nota crédito en Factus antes de anular.
                </div>
              )}
              <div>
                <label className="text-xs font-semibold text-slate-500">
                  No. factura nueva (si aplica)
                </label>
                <input
                  value={anulacionData.numeroNuevaFactura}
                  onChange={(event) =>
                    setAnulacionData((prev) => ({
                      ...prev,
                      numeroNuevaFactura: event.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-2 text-sm"
                  placeholder="Prefijo y número"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={anulacionData.devuelveInventario}
                  onChange={(event) =>
                    setAnulacionData((prev) => ({
                      ...prev,
                      devuelveInventario: event.target.checked,
                    }))
                  }
                />
                La mercancía regresa al inventario
              </label>
            </div>
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={confirmarAnulacion}
                className="rounded bg-slate-200 px-6 py-2 text-sm font-semibold uppercase text-slate-700 disabled:opacity-50"
                disabled={anulando}
              >
                {anulando && anulacionRequiereNotaCredito
                  ? 'Emitiendo nota crédito...'
                  : anulando
                    ? 'Anulando...'
                    : 'Anular'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
