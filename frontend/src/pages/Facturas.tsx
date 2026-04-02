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
    return { prefijo: numeroComprobante.slice(0, 3), numero: numeroComprobante };
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

export default function Facturas() {
  const { showNotification } = useNotification();
  const today = getLocalDateInputValue();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [facturas, setFacturas] = useState<FacturaItem[]>([]);
  const [busqueda, setBusqueda] = useState('');
  const [estadoFiltro, setEstadoFiltro] = useState<'FACTURADA' | 'ANULADA' | 'TODAS'>(
    'FACTURADA'
  );
  const [fechaInicio, setFechaInicio] = useState(today);
  const [fechaFin, setFechaFin] = useState(today);
  const [filtrosAplicados, setFiltrosAplicados] = useState({
    estado: 'FACTURADA' as 'FACTURADA' | 'ANULADA' | 'TODAS',
    fechaInicio: today,
    fechaFin: today,
  });
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
      const facturasElectronicas = await facturacionApi.getFacturas();
      const porNumero = new Map(
        facturasElectronicas.map((item) => [String(item.numero).trim(), item])
      );
      setFacturas(
        response.map((venta) => {
          const mapped = mapVentaToFacturaItem(venta);
          const numeroCompleto = venta.numero_comprobante ?? '';
          return {
            ...mapped,
            electronica: porNumero.get(numeroCompleto) ?? porNumero.get(mapped.numero) ?? undefined,
          };
        })
      );
      setSelectedIds([]);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
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
      return matchesSearch && matchesInicio && matchesFin;
    });
  }, [busqueda, facturas, fechaInicio, fechaFin]);

  useEffect(() => {
    cargarFacturas(filtrosAplicados);
    return () => {
      ventasAbortRef.current?.abort();
    };
  }, [filtrosAplicados]);

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
    if (!numero) {
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
        await facturacionApi.descargarXML(numero);
      } else if (action === 'pdf') {
        await facturacionApi.descargarPDF(numero);
      } else {
        await facturacionApi.enviarFacturaCorreo(numero);
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
      showNotification({
        type: 'success',
        message: numeroNotaCredito
          ? `Factura anulada. Nota crédito emitida: ${numeroNotaCredito}.`
          : 'Factura anulada correctamente.',
      });
      await cargarFacturas({
        ...filtrosAplicados,
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
    <div className="space-y-4 px-6 py-6">
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
                cargarFacturas({
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
            <label className="text-xs font-semibold text-slate-500">Fecha final</label>
            <input
              type="date"
              value={fechaFin}
              onChange={(event) => setFechaFin(event.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1 self-end">
            <button
              type="button"
              onClick={() =>
                setFiltrosAplicados({
                  estado: estadoFiltro,
                  fechaInicio,
                  fechaFin,
                })
              }
              className="rounded bg-blue-600 px-3 py-2 text-xs font-semibold uppercase text-white hover:bg-blue-700"
            >
              Aplicar filtros
            </button>
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
                      checked={selectedIds.length === facturasFiltradas.length && facturasFiltradas.length > 0}
                      onChange={(event) =>
                        setSelectedIds(
                          event.target.checked ? facturasFiltradas.map((item) => item.id) : []
                        )
                      }
                    />
                  </th>
                  <th className="px-2 py-2 text-left">Prefijo</th>
                  <th className="px-2 py-2 text-left">Factura</th>
                  <th className="px-2 py-2 text-left">Fecha/Hora</th>
                  <th className="px-2 py-2 text-left">Estado</th>
                  <th className="px-2 py-2 text-left">Electrónica</th>
                  <th className="px-2 py-2 text-left">Medio/Pago</th>
                  <th className="px-2 py-2 text-right">Total</th>
                  <th className="px-2 py-2 text-left">NIT/CC</th>
                  <th className="px-2 py-2 text-left">Cliente</th>
                  <th className="px-2 py-2 text-left">Usuario</th>
                  <th className="px-2 py-2 text-left">CUFE / Ref</th>
                  <th className="px-2 py-2 text-left">Acciones FE</th>
                </tr>
              </thead>
              <tbody>
                {cargando && (
                  <tr>
                    <td colSpan={13} className="px-4 py-6 text-center text-sm text-slate-500">
                      Cargando facturas...
                    </td>
                  </tr>
                )}
                {!cargando &&
                  facturasFiltradas.map((factura) => {
                    const selected = selectedIds.includes(factura.id);
                    return (
                      <tr
                        key={factura.id}
                        className={`border-t border-slate-200 ${
                          selected ? 'bg-blue-100' : 'bg-white'
                        }`}
                      >
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleSelect(factura.id)}
                          />
                        </td>
                        <td className="px-2 py-2 font-semibold text-slate-700">
                          {factura.prefijo}
                        </td>
                        <td className="px-2 py-2 text-slate-700">{factura.numero}</td>
                        <td className="px-2 py-2 text-slate-600">{factura.fechaHora}</td>
                        <td className="px-2 py-2 text-slate-600">{factura.estadoDisplay}</td>
                        <td className="px-2 py-2 text-slate-600">
                          {factura.electronica ? resolveEstadoFactura(factura.electronica) : 'Local'}
                        </td>
                        <td className="px-2 py-2 text-slate-600">{factura.medioPagoDisplay}</td>
                        <td className="px-2 py-2 text-right text-rose-600">
                          {currencyFormatter.format(factura.total)}
                        </td>
                        <td className="px-2 py-2 text-slate-600">{factura.nitCc}</td>
                        <td className="px-2 py-2 text-slate-600">{factura.cliente}</td>
                        <td className="px-2 py-2 text-slate-600">{factura.usuario}</td>
                        <td className="px-2 py-2 text-[11px] text-slate-600">
                          {factura.electronica ? (
                            <div>
                              <p className="truncate">CUFE: {factura.electronica.cufe ?? 'N/D'}</p>
                              <p className="truncate">Ref: {factura.electronica.numero}</p>
                              {factura.electronica.observaciones ? (
                                <p className="truncate text-amber-700">
                                  Obs: {factura.electronica.observaciones}
                                </p>
                              ) : null}
                              {factura.electronica.public_url ? (
                                <a
                                  href={factura.electronica.public_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="truncate text-blue-600 underline"
                                >
                                  Ver en DIAN/Factus
                                </a>
                              ) : null}
                            </div>
                          ) : (
                            'Sin emisión FE'
                          )}
                        </td>
                        <td className="px-2 py-2">
                          {factura.electronica ? (
                            <div className="flex flex-wrap gap-1">
                              <button
                                type="button"
                                className="rounded bg-blue-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[factura.electronica.numero])}
                                onClick={() => handleAccionElectronica(factura, 'estado')}
                              >
                                Estado
                              </button>
                              <button
                                type="button"
                                className="rounded bg-indigo-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[factura.electronica.numero])}
                                onClick={() => handleAccionElectronica(factura, 'xml')}
                              >
                                XML
                              </button>
                              <button
                                type="button"
                                className="rounded bg-violet-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[factura.electronica.numero])}
                                onClick={() => handleAccionElectronica(factura, 'pdf')}
                              >
                                PDF
                              </button>
                              <button
                                type="button"
                                className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-semibold text-white disabled:opacity-50"
                                disabled={Boolean(accionesElectronicas[factura.electronica.numero])}
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
                    <td colSpan={13} className="px-4 py-6 text-center text-sm text-slate-500">
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
                      ivaPorcentaje: Number(detalle.iva_porcentaje),
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
                      ivaPorcentaje: Number(item.iva_porcentaje),
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
