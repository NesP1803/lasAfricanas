import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useNotification } from '../../../contexts/NotificationContext';
import { notasCreditoApi, type CrearNotaCreditoPayload, type NotaCredito } from '../services/notasCreditoApi';
import EstadoNotaCreditoBadge from '../components/EstadoNotaCreditoBadge';

interface FacturaOption {
  id: number;
  ventaId: number;
  numero: string;
  cliente: string;
  fecha: string;
  total: number;
  cufe?: string;
  estado: string;
}

interface EditableLine {
  detalleId: number;
  productoNombre: string;
  codigo: string;
  cantidadFacturada: number;
  cantidadYaAcreditada: number;
  disponible: number;
  precioUnitario: number;
  impuestoPorcentaje: number;
  cantidadAcreditar: number;
  afectaInventario: boolean;
  motivoLinea: string;
  selected: boolean;
}

interface MotivoOption {
  code: string;
  label: string;
  description: string;
}

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

const toNumber = (value: string | number | undefined | null) => {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
};

const formatFecha = (fecha: string) => {
  const date = new Date(fecha);
  if (Number.isNaN(date.getTime())) return fecha;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
};

const steps = ['Factura origen', 'Tipo y motivo', 'Líneas o alcance', 'Confirmación'];

const motivosCredito: MotivoOption[] = [
  {
    code: 'ANULACION_TOTAL_DESISTIMIENTO',
    label: 'Anulación total (desistimiento)',
    description: 'Revierte completamente la operación por desistimiento del cliente.',
  },
  {
    code: 'DEVOLUCION_PRODUCTOS',
    label: 'Devolución de productos (total o parcial)',
    description: 'Se usa cuando hay devolución física o reversión de unidades facturadas.',
  },
  {
    code: 'DESCUENTO_REBAJA_POSTERIOR',
    label: 'Descuento o rebaja posterior a la venta',
    description: 'Aplica cuando se concede un descuento después de facturar.',
  },
  {
    code: 'CORRECCION_PRECIOS_DESCRIPCIONES',
    label: 'Corrección de errores en precios o descripciones',
    description: 'Corrige datos comerciales mal registrados en la factura original.',
  },
];

const extractErrorMessage = (error: unknown, fallback: string) => {
  if (error && typeof error === 'object') {
    const payload = error as { response?: { data?: unknown } };
    const responseData = payload.response?.data;
    if (responseData && typeof responseData === 'object') {
      const data = responseData as Record<string, unknown>;
      const direct = [data.detail, data.message, data.error].find((item) => typeof item === 'string' && item.trim());
      if (typeof direct === 'string') return direct;
    }
  }
  return fallback;
};

export default function CrearNotaCreditoPage() {
  const navigate = useNavigate();
  const { showNotification } = useNotification();

  const [loading, setLoading] = useState(false);
  const [loadingFacturas, setLoadingFacturas] = useState(false);
  const [facturas, setFacturas] = useState<FacturaOption[]>([]);
  const [notasExistentes, setNotasExistentes] = useState<NotaCredito[]>([]);
  const [busquedaFactura, setBusquedaFactura] = useState('');
  const [facturaSeleccionadaId, setFacturaSeleccionadaId] = useState<number | null>(null);
  const [tipoNota, setTipoNota] = useState<'PARCIAL' | 'TOTAL'>('PARCIAL');
  const [lineas, setLineas] = useState<EditableLine[]>([]);
  const [motivoTipo, setMotivoTipo] = useState(motivosCredito[1].code);
  const [motivo, setMotivo] = useState('');
  const [observaciones, setObservaciones] = useState('');

  useEffect(() => {
    const loadInitialData = async () => {
      setLoadingFacturas(true);
      try {
        const [facturasResp, notasResp] = await Promise.all([
          notasCreditoApi.getFacturasElectronicas(),
          notasCreditoApi.getNotasCredito(),
        ]);
        setFacturas(
          facturasResp.map((f) => ({
            id: f.id,
            ventaId: Number(f.venta_id || 0),
            numero: f.numero,
            cliente: f.cliente,
            fecha: f.fecha,
            total: Number(f.total || 0),
            cufe: f.cufe,
            estado: String(f.estado_electronico || f.estado || 'PENDIENTE_REINTENTO'),
          })),
        );
        setNotasExistentes(notasResp);
      } catch {
        showNotification({ message: 'No fue posible cargar facturas origen.', type: 'error', durationMs: 2500 });
      } finally {
        setLoadingFacturas(false);
      }
    };

    loadInitialData();
  }, [showNotification]);

  const facturasFiltradas = useMemo(() => {
    const q = busquedaFactura.trim().toLowerCase();
    return facturas.filter((f) => !q || `${f.numero} ${f.cliente}`.toLowerCase().includes(q));
  }, [facturas, busquedaFactura]);

  const facturaSeleccionada = useMemo(
    () => facturas.find((factura) => factura.id === facturaSeleccionadaId) || null,
    [facturas, facturaSeleccionadaId],
  );

  const notasPreviasFactura = useMemo(
    () => notasExistentes.filter((nota) => nota.factura_asociada === facturaSeleccionada?.numero),
    [notasExistentes, facturaSeleccionada],
  );

  const hasParcialesPreviasActivas = useMemo(
    () =>
      notasPreviasFactura.some(
        (nota) =>
          (nota.tipo_nota || '').toUpperCase() === 'PARCIAL' &&
          ['ACEPTADA', 'ENVIADA_A_FACTUS'].includes((nota.estado_local || '').toUpperCase()),
      ),
    [notasPreviasFactura],
  );

  useEffect(() => {
    if (hasParcialesPreviasActivas && tipoNota === 'TOTAL') {
      setTipoNota('PARCIAL');
    }
  }, [hasParcialesPreviasActivas, tipoNota]);

  const loadVentaLines = async (factura: FacturaOption) => {
    if (!factura.ventaId) {
      showNotification({
        message: 'La factura seleccionada no tiene venta asociada para cargar líneas.',
        type: 'error',
        durationMs: 2500,
      });
      return;
    }
    setLoading(true);
    try {
      const venta = await notasCreditoApi.getVenta(factura.ventaId);
      const acumulado = new Map<number, number>();
      notasExistentes.forEach((nota) => {
        const aplica =
          nota.factura_asociada === factura.numero &&
          ['ACEPTADA', 'ENVIADA_A_FACTUS'].includes((nota.estado_local || '').toUpperCase());
        if (!aplica) return;
        (nota.detalles || []).forEach((linea) => {
          acumulado.set(
            linea.detalle_venta_original,
            (acumulado.get(linea.detalle_venta_original) || 0) + toNumber(linea.cantidad_a_acreditar),
          );
        });
      });

      const editable = venta.detalles.map((detail) => {
        const facturada = toNumber(detail.cantidad);
        const acreditada = acumulado.get(detail.id) || 0;
        const disponible = Math.max(0, facturada - acreditada);
        return {
          detalleId: detail.id,
          productoNombre: detail.producto_nombre || `Producto #${detail.producto}`,
          codigo: detail.producto_codigo || 'N/D',
          cantidadFacturada: facturada,
          cantidadYaAcreditada: acreditada,
          disponible,
          precioUnitario: toNumber(detail.precio_unitario),
          impuestoPorcentaje: toNumber(detail.iva_porcentaje),
          cantidadAcreditar: disponible > 0 ? 1 : 0,
          afectaInventario: true,
          motivoLinea: '',
          selected: false,
        } as EditableLine;
      });
      setLineas(editable);
    } catch {
      setLineas([]);
      showNotification({
        message: 'No fue posible cargar productos de la factura origen.',
        type: 'error',
        durationMs: 2500,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFactura = (id: number) => {
    setFacturaSeleccionadaId(id);
    setLineas([]);
    const factura = facturas.find((item) => item.id === id);
    if (factura) loadVentaLines(factura);
  };

  const selectedLines = useMemo(
    () => lineas.filter((linea) => linea.selected && linea.disponible > 0),
    [lineas],
  );

  const resumen = useMemo(() => {
    const workingLines =
      tipoNota === 'TOTAL'
        ? lineas
            .filter((linea) => linea.disponible > 0)
            .map((linea) => ({ ...linea, cantidadAcreditar: linea.disponible }))
        : selectedLines;
    const subtotal = workingLines.reduce(
      (acc, linea) => acc + linea.cantidadAcreditar * linea.precioUnitario,
      0,
    );
    const impuestos = workingLines.reduce(
      (acc, linea) =>
        acc + linea.cantidadAcreditar * linea.precioUnitario * (linea.impuestoPorcentaje / 100),
      0,
    );
    const unidades = workingLines.reduce((acc, linea) => acc + linea.cantidadAcreditar, 0);
    return {
      subtotal,
      impuestos,
      total: subtotal + impuestos,
      lineas: workingLines.length,
      unidades,
      devuelveStock: workingLines.some((linea) => linea.afectaInventario),
    };
  }, [selectedLines, lineas, tipoNota]);

  const currentStep = useMemo(() => {
    if (!facturaSeleccionada) return 0;
    if (!motivo.trim()) return 1;
    if (tipoNota === 'PARCIAL' && selectedLines.length === 0) return 2;
    return 3;
  }, [facturaSeleccionada, motivo, tipoNota, selectedLines.length]);

  const motivoCompuesto = useMemo(() => {
    const motivoLabel = motivosCredito.find((item) => item.code === motivoTipo)?.label || motivoTipo;
    return `${motivoLabel}. ${motivo.trim()}${observaciones.trim() ? ` | Observaciones: ${observaciones.trim()}` : ''}`;
  }, [motivoTipo, motivo, observaciones]);

  const validar = () => {
    if (!facturaSeleccionada) {
      showNotification({ message: 'Debes seleccionar una factura origen.', type: 'error', durationMs: 2500 });
      return false;
    }
    if (!motivo.trim()) {
      showNotification({ message: 'Debes registrar el motivo de la nota crédito.', type: 'error', durationMs: 2500 });
      return false;
    }
    if (tipoNota === 'TOTAL' && hasParcialesPreviasActivas) {
      showNotification({
        message: 'No se puede emitir total después de acreditaciones parciales previas.',
        type: 'error',
        durationMs: 2800,
      });
      return false;
    }
    if (tipoNota === 'PARCIAL') {
      if (selectedLines.length === 0) {
        showNotification({ message: 'Debes seleccionar al menos un producto.', type: 'error', durationMs: 2500 });
        return false;
      }
      const excedidas = selectedLines.some(
        (linea) => linea.cantidadAcreditar <= 0 || linea.cantidadAcreditar > linea.disponible,
      );
      if (excedidas) {
        showNotification({
          message: 'La cantidad excede el saldo disponible.',
          type: 'error',
          durationMs: 2500,
        });
        return false;
      }
    }
    return true;
  };

  const handleEmitir = async () => {
    if (!validar() || !facturaSeleccionada) return;
    setLoading(true);
    try {
      if (tipoNota === 'TOTAL') {
        await notasCreditoApi.crearNotaCreditoTotal(
          facturaSeleccionada.id,
          motivoCompuesto,
          resumen.devuelveStock,
        );
      } else {
        const payload: CrearNotaCreditoPayload = {
          motivo: motivoCompuesto,
          lines: selectedLines.map((linea) => ({
            detalle_venta_original_id: linea.detalleId,
            cantidad_a_acreditar: linea.cantidadAcreditar,
            afecta_inventario: linea.afectaInventario,
            motivo_linea: linea.motivoLinea || undefined,
          })),
        };
        await notasCreditoApi.crearNotaCreditoParcial(facturaSeleccionada.id, payload);
      }
      showNotification({
        message: 'Nota crédito emitida correctamente.',
        type: 'success',
        durationMs: 2200,
      });
      navigate('/listados/notas-credito');
    } catch (error) {
      showNotification({
        message: extractErrorMessage(error, 'No fue posible emitir la nota crédito.'),
        type: 'error',
        durationMs: 3000,
      });
      console.error('Error al emitir nota crédito', error);
    } finally {
      setLoading(false);
    }
  };


  const motivoSeleccionado = motivosCredito.find((item) => item.code === motivoTipo);

  return (
    <div className="space-y-4 px-6 py-6">
      <div className="rounded-xl bg-white p-5 shadow">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
              Facturación / Notas crédito / Crear
            </p>
            <h2 className="text-3xl font-semibold text-slate-900">Crear nota crédito</h2>
            <p className="text-sm text-slate-500">
              Flujo guiado para reversar parcialmente o totalmente una factura de forma segura.
            </p>
          </div>
          <Link
            to="/listados/notas-credito"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Volver al listado
          </Link>
        </div>

        <ol className="mt-4 grid gap-2 text-xs sm:grid-cols-4">
          {steps.map((step, index) => (
            <li
              key={step}
              className={`rounded-md border px-3 py-2 ${
                index <= currentStep
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-slate-200 text-slate-500'
              }`}
            >
              {index + 1}. {step}
            </li>
          ))}
        </ol>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">1) Seleccionar factura origen</h3>
            <p className="mb-3 text-sm text-slate-500">
              Busca por número o cliente y elige la factura que deseas corregir.
            </p>
            <input
              value={busquedaFactura}
              onChange={(event) => setBusquedaFactura(event.target.value)}
              placeholder="Buscar factura o cliente"
              className="mb-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <div className="max-h-60 overflow-auto rounded-md border border-slate-200">
              {loadingFacturas ? (
                <p className="p-4 text-sm text-slate-500">Cargando facturas…</p>
              ) : (
                facturasFiltradas.map((factura) => (
                  <button
                    type="button"
                    key={factura.id}
                    onClick={() => handleSelectFactura(factura.id)}
                    className={`flex w-full items-center justify-between border-b border-slate-100 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                      facturaSeleccionadaId === factura.id ? 'bg-blue-50' : ''
                    }`}
                  >
                    <span>
                      <span className="font-semibold text-slate-800">{factura.numero}</span>
                      <span className="ml-2 text-slate-600">{factura.cliente}</span>
                    </span>
                    <span className="text-slate-500">{money.format(factura.total)}</span>
                  </button>
                ))
              )}
            </div>

            {facturaSeleccionada && (
              <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-4">
                <p className="text-sm font-semibold text-blue-900">
                  Factura seleccionada: {facturaSeleccionada.numero}
                </p>
                <div className="mt-2 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                  <p>
                    <strong>Cliente:</strong> {facturaSeleccionada.cliente}
                  </p>
                  <p>
                    <strong>Fecha:</strong> {formatFecha(facturaSeleccionada.fecha)}
                  </p>
                  <p>
                    <strong>Total:</strong> {money.format(facturaSeleccionada.total)}
                  </p>
                  <p>
                    <strong>CUFE:</strong> {facturaSeleccionada.cufe || 'No disponible'}
                  </p>
                  <p className="sm:col-span-2">
                    <strong>Estado electrónico:</strong>{' '}
                    <EstadoNotaCreditoBadge estado={facturaSeleccionada.estado} />
                  </p>
                  <p className="sm:col-span-2">
                    <strong>Notas crédito previas:</strong> {notasPreviasFactura.length}
                  </p>
                </div>
              </div>
            )}
          </section>

          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">2) Tipo de nota y motivo</h3>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <button
                type="button"
                onClick={() => setTipoNota('PARCIAL')}
                className={`rounded-lg border p-4 text-left ${
                  tipoNota === 'PARCIAL' ? 'border-blue-500 bg-blue-50' : 'border-slate-200'
                }`}
              >
                <p className="font-semibold text-slate-900">Nota crédito parcial</p>
                <p className="text-sm text-slate-600">
                  Úsala para reversar uno o varios productos, con control por cantidad y stock.
                </p>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (hasParcialesPreviasActivas) {
                    showNotification({
                      message: 'No puedes elegir total: la factura ya tiene acreditaciones parciales activas.',
                      type: 'error',
                      durationMs: 2800,
                    });
                    return;
                  }
                  setTipoNota('TOTAL');
                }}
                className={`rounded-lg border p-4 text-left ${
                  tipoNota === 'TOTAL' ? 'border-blue-500 bg-blue-50' : 'border-slate-200'
                }`}
              >
                <p className="font-semibold text-slate-900">Nota crédito total</p>
                <p className="text-sm text-slate-600">
                  Revierte toda la factura en una sola operación guiada y confirmada.
                </p>
              </button>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <label className="text-sm text-slate-700 md:col-span-2">
                Tipo de corrección
                <select
                  value={motivoTipo}
                  onChange={(event) => setMotivoTipo(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                >
                  {motivosCredito.map((motivoOption) => (
                    <option key={motivoOption.code} value={motivoOption.code}>
                      {motivoOption.label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 md:col-span-2">
                {motivoSeleccionado?.description}
              </p>
              <label className="text-sm text-slate-700 md:col-span-2">
                Motivo general*
                <textarea
                  value={motivo}
                  onChange={(event) => setMotivo(event.target.value)}
                  placeholder="Describe claramente qué estás corrigiendo"
                  className="mt-1 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="text-sm text-slate-700 md:col-span-2">
                Observaciones
                <input
                  value={observaciones}
                  onChange={(event) => setObservaciones(event.target.value)}
                  placeholder="Opcional"
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
                />
              </label>
            </div>
          </section>

          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">
              3) {tipoNota === 'TOTAL' ? 'Alcance total' : 'Selección de productos'}
            </h3>
            {tipoNota === 'TOTAL' ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Esta acción acreditará todas las líneas disponibles de la factura. Solo debes confirmar
                motivo e inventario.
              </div>
            ) : (
              <div className="mt-3 overflow-auto rounded-md border border-slate-200">
                <table className="min-w-[980px] divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                    <tr>
                      <th className="px-3 py-2">Sel.</th>
                      <th className="px-3 py-2">Producto</th>
                      <th className="px-3 py-2">Código</th>
                      <th className="px-3 py-2">Facturada</th>
                      <th className="px-3 py-2">Ya acreditada</th>
                      <th className="px-3 py-2">Disponible</th>
                      <th className="px-3 py-2">Precio</th>
                      <th className="px-3 py-2">Impuesto</th>
                      <th className="px-3 py-2">A acreditar</th>
                      <th className="px-3 py-2">Devuelve inventario</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {lineas.map((linea) => (
                      <tr
                        key={linea.detalleId}
                        className={linea.disponible <= 0 ? 'bg-slate-50 text-slate-400' : ''}
                      >
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            disabled={linea.disponible <= 0}
                            checked={linea.selected}
                            onChange={(event) =>
                              setLineas((prev) =>
                                prev.map((item) =>
                                  item.detalleId === linea.detalleId
                                    ? { ...item, selected: event.target.checked }
                                    : item,
                                ),
                              )
                            }
                          />
                        </td>
                        <td className="px-3 py-2">{linea.productoNombre}</td>
                        <td className="px-3 py-2">{linea.codigo}</td>
                        <td className="px-3 py-2">{linea.cantidadFacturada}</td>
                        <td className="px-3 py-2">{linea.cantidadYaAcreditada}</td>
                        <td className="px-3 py-2 font-semibold">{linea.disponible}</td>
                        <td className="px-3 py-2">{money.format(linea.precioUnitario)}</td>
                        <td className="px-3 py-2">{linea.impuestoPorcentaje}%</td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            min={0}
                            max={linea.disponible}
                            step="0.01"
                            value={linea.cantidadAcreditar}
                            disabled={!linea.selected || linea.disponible <= 0}
                            onChange={(event) => {
                              const nuevaCantidad = Number(event.target.value || 0);
                              setLineas((prev) =>
                                prev.map((item) =>
                                  item.detalleId === linea.detalleId
                                    ? { ...item, cantidadAcreditar: nuevaCantidad }
                                    : item,
                                ),
                              );
                            }}
                            className="w-24 rounded-md border border-slate-300 px-2 py-1"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={linea.afectaInventario}
                            disabled={!linea.selected || linea.disponible <= 0}
                            onChange={(event) =>
                              setLineas((prev) =>
                                prev.map((item) =>
                                  item.detalleId === linea.detalleId
                                    ? { ...item, afectaInventario: event.target.checked }
                                    : item,
                                ),
                              )
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-xl bg-white p-5 shadow">
            <h3 className="text-lg font-semibold text-slate-800">4) Confirmación</h3>
            <p className="mt-2 text-sm text-slate-600">Verifica resumen final antes de emitir a Factus.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleEmitir}
                disabled={loading}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {loading ? 'Emitiendo...' : 'Emitir nota crédito'}
              </button>
              <button
                type="button"
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
                onClick={() =>
                  showNotification({
                    message: 'Borrador local pendiente de implementar en backend.',
                    type: 'info',
                    durationMs: 2200,
                  })
                }
              >
                Guardar borrador
              </button>
            </div>
          </section>
        </div>

        <aside className="h-fit rounded-xl bg-white p-5 shadow xl:sticky xl:top-4">
          <h3 className="text-lg font-semibold text-slate-800">Resumen de impacto</h3>
          <div className="mt-3 space-y-2 text-sm text-slate-700">
            <p>
              <strong>Factura origen:</strong> {facturaSeleccionada?.numero || 'Sin seleccionar'}
            </p>
            <p>
              <strong>Tipo:</strong> {tipoNota === 'TOTAL' ? 'Nota crédito total' : 'Nota crédito parcial'}
            </p>
            <p>
              <strong>Tipo de corrección:</strong>{' '}
              {motivosCredito.find((item) => item.code === motivoTipo)?.label || 'No definido'}
            </p>
            <p>
              <strong>Subtotal acreditado:</strong> {money.format(resumen.subtotal)}
            </p>
            <p>
              <strong>Impuestos acreditados:</strong> {money.format(resumen.impuestos)}
            </p>
            <p>
              <strong>Total nota crédito:</strong> {money.format(resumen.total)}
            </p>
            <p>
              <strong>Líneas afectadas:</strong> {resumen.lineas}
            </p>
            <p>
              <strong>Unidades:</strong> {resumen.unidades}
            </p>
            <p>
              <strong>Devuelve stock:</strong> {resumen.devuelveStock ? 'Sí' : 'No'}
            </p>
            <p>
              <strong>Estado esperado factura:</strong>{' '}
              {tipoNota === 'TOTAL' ? 'CREDITADA_TOTAL' : 'CREDITADA_PARCIAL'}
            </p>
          </div>
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            Al emitir, la nota se envía a Factus y se actualiza trazabilidad local/remota según respuesta.
          </div>
        </aside>
      </div>
    </div>
  );
}
