import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Barcode,
  CircleDollarSign,
  FileText,
  MinusCircle,
  PlusCircle,
  Search,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react';
import { inventarioApi, type Producto, type ProductoList } from '../api/inventario';
import { ventasApi } from '../api/ventas';
import { configuracionAPI } from '../api/configuracion';
import { useAuth } from '../contexts/AuthContext';
import ComprobanteTemplate, {
  type DocumentoDetalle,
} from '../components/ComprobanteTemplate';
import type { ConfiguracionEmpresa } from '../types';
import type { ConfiguracionFacturacion } from '../types';

type CartItem = {
  id: number;
  codigo: string;
  nombre: string;
  ivaPorcentaje: number;
  precioUnitario: number;
  stock: number;
  cantidad: number;
  descuentoPorcentaje: number;
};

type DocumentoGenerado = {
  tipo: 'COTIZACION' | 'REMISION' | 'FACTURA';
  numero: string;
  cliente: string;
  total: string;
};

type DocumentoPreview = {
  tipo: 'COTIZACION' | 'REMISION' | 'FACTURA';
  formato: 'POS' | 'CARTA';
  numero: string;
  fecha: string;
  clienteNombre: string;
  clienteDocumento: string;
  medioPago: string;
  estado: string;
  detalles: DocumentoDetalle[];
  subtotal: number;
  descuento: number;
  iva: number;
  total: number;
  efectivoRecibido: number;
  cambio: number;
};

type TallerVentaPayload = {
  ordenId: number;
  motoId: number;
  motoPlaca?: string;
  motoMarca?: string;
  motoModelo?: string;
  clienteId: number | null;
  clienteNombre: string;
  repuestos: Array<{
    productoId: number;
    codigo: string;
    nombre: string;
    cantidad: number;
    precioUnitario: string;
    ivaPorcentaje: string;
  }>;
};

const currencyFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
});

const parseNumber = (value: string) => {
  const normalized = value.replace(/[^\d.-]/g, '');
  const parsed = Number(normalized);
  return Number.isNaN(parsed) ? 0 : parsed;
};

export default function Ventas() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [configuracion, setConfiguracion] = useState<ConfiguracionFacturacion | null>(null);
  const [empresa, setEmpresa] = useState<ConfiguracionEmpresa | null>(null);
  const [clienteDocumento, setClienteDocumento] = useState('');
  const [clienteNombre, setClienteNombre] = useState('Cliente general');
  const [clienteId, setClienteId] = useState<number | null>(null);
  const [productos, setProductos] = useState<ProductoList[]>([]);
  const [busquedaProducto, setBusquedaProducto] = useState('');
  const [codigoProducto, setCodigoProducto] = useState('');
  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [descuentoGeneral, setDescuentoGeneral] = useState('0');
  const [descuentoAutorizado, setDescuentoAutorizado] = useState(false);
  const [aprobadorId, setAprobadorId] = useState('');
  const [medioPago, setMedioPago] = useState<'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO'>('EFECTIVO');
  const [efectivoRecibido, setEfectivoRecibido] = useState('0');
  const [documentoGenerado, setDocumentoGenerado] = useState<DocumentoGenerado | null>(null);
  const [documentoPreview, setDocumentoPreview] = useState<DocumentoPreview | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [mostrarBusqueda, setMostrarBusqueda] = useState(false);
  const [mostrarPermiso, setMostrarPermiso] = useState(false);
  const [usuariosAprobadores, setUsuariosAprobadores] = useState<{ id: number; nombre: string }[]>([]);
  const codigoInputRef = useRef<HTMLInputElement | null>(null);

  const tallerPayload = useMemo(() => {
    const state = location.state as { fromTaller?: TallerVentaPayload } | null;
    return state?.fromTaller ?? null;
  }, [location.state]);

  useEffect(() => {
    configuracionAPI
      .obtenerFacturacion()
      .then(setConfiguracion)
      .catch(() => setConfiguracion(null));
    configuracionAPI
      .obtenerEmpresa()
      .then(setEmpresa)
      .catch(() => setEmpresa(null));
  }, []);

  useEffect(() => {
    if (!mostrarBusqueda) return;
    inventarioApi
      .getProductos({ search: busquedaProducto })
      .then((response) => setProductos(response.results ?? []))
      .catch(() => setProductos([]));
  }, [busquedaProducto, mostrarBusqueda]);

  useEffect(() => {
    if (mostrarPermiso && usuariosAprobadores.length === 0) {
      configuracionAPI
        .obtenerUsuarios()
        .then((data) =>
          setUsuariosAprobadores(
            data.map((usuario) => ({
              id: usuario.id,
              nombre: `${usuario.first_name} ${usuario.last_name}`.trim() || usuario.username,
            }))
          )
        )
        .catch(() => setUsuariosAprobadores([]));
    }
  }, [mostrarPermiso, usuariosAprobadores.length]);

  useEffect(() => {
    codigoInputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!tallerPayload) return;
    const applyTallerData = async () => {
      try {
        const productos = await Promise.all(
          tallerPayload.repuestos.map((repuesto) =>
            inventarioApi
              .getProducto(repuesto.productoId)
              .then((producto) => ({ producto, repuesto }))
              .catch(() => ({ producto: null, repuesto }))
          )
        );

        const items = productos.map(({ producto, repuesto }) => ({
          id: repuesto.productoId,
          codigo: repuesto.codigo || producto?.codigo || '',
          nombre: repuesto.nombre || producto?.nombre || 'Producto',
          ivaPorcentaje: Number(repuesto.ivaPorcentaje || producto?.iva_porcentaje || 0),
          precioUnitario: Number(repuesto.precioUnitario || producto?.precio_venta || 0),
          stock: producto?.stock ?? 0,
          cantidad: repuesto.cantidad,
          descuentoPorcentaje: 0,
        }));

        setCartItems(items);

        if (tallerPayload.clienteId) {
          try {
            const cliente = await ventasApi.getCliente(tallerPayload.clienteId);
            setClienteDocumento(cliente.numero_documento);
            setClienteNombre(cliente.nombre);
            setClienteId(cliente.id);
          } catch (error) {
            setClienteNombre(tallerPayload.clienteNombre || 'Cliente general');
            setClienteId(tallerPayload.clienteId ?? null);
            setMensaje('No se pudo cargar el cliente desde la orden de taller.');
          }
        } else {
          setClienteNombre(tallerPayload.clienteNombre || 'Cliente general');
          setClienteId(null);
          if (!tallerPayload.clienteNombre) {
            setMensaje('La orden no tiene cliente asignado.');
          }
        }
      } finally {
        navigate('/ventas', { replace: true, state: null });
      }
    };

    applyTallerData();
  }, [tallerPayload, navigate]);

  const totals = useMemo(() => {
    const subtotal = cartItems.reduce(
      (acc, item) => acc + item.precioUnitario * item.cantidad,
      0
    );
    const descuentoLineas = cartItems.reduce((acc, item) => {
      const lineSubtotal = item.precioUnitario * item.cantidad;
      return acc + lineSubtotal * (item.descuentoPorcentaje / 100);
    }, 0);
    const descuentoGeneralValor = descuentoAutorizado
      ? subtotal * (parseNumber(descuentoGeneral) / 100)
      : 0;
    const iva = cartItems.reduce((acc, item) => {
      const lineSubtotal = item.precioUnitario * item.cantidad;
      const lineDesc = lineSubtotal * (item.descuentoPorcentaje / 100);
      const base = lineSubtotal - lineDesc;
      return acc + base * (item.ivaPorcentaje / 100);
    }, 0);
    const descuentoTotal = descuentoLineas + descuentoGeneralValor;
    const total = subtotal - descuentoTotal + iva;
    return {
      subtotal,
      descuentoTotal,
      descuentoGeneralValor,
      iva,
      total,
    };
  }, [cartItems, descuentoAutorizado, descuentoGeneral]);

  const handleBuscarCliente = async () => {
    if (!clienteDocumento.trim()) return;
    try {
      const cliente = await ventasApi.buscarCliente(clienteDocumento.trim());
      setClienteNombre(cliente.nombre);
      setClienteId(cliente.id);
      setMensaje(null);
    } catch (error) {
      setMensaje('Cliente no encontrado. Regístralo desde Listados.');
      setClienteNombre('Cliente general');
      setClienteId(null);
    }
  };

  const agregarProducto = (producto: Producto) => {
    setCartItems((prev) => {
      const existing = prev.find((item) => item.id === producto.id);
      if (existing) {
        return prev.map((item) =>
          item.id === producto.id
            ? { ...item, cantidad: item.cantidad + 1 }
            : item
        );
      }
      return [
        ...prev,
        {
          id: producto.id,
          codigo: producto.codigo,
          nombre: producto.nombre,
          ivaPorcentaje: Number(producto.iva_porcentaje ?? 0),
          precioUnitario: Number(producto.precio_venta),
          stock: producto.stock,
          cantidad: 1,
          descuentoPorcentaje: 0,
        },
      ];
    });
  };

  const handleBuscarProductoPorCodigo = async () => {
    if (!codigoProducto.trim()) return;
    try {
      const producto = await inventarioApi.buscarPorCodigo(codigoProducto.trim());
      agregarProducto(producto);
      setCodigoProducto('');
      setMensaje(null);
      codigoInputRef.current?.focus();
    } catch (error) {
      setMensaje('Producto no encontrado.');
    }
  };

  const handleAbrirBusqueda = () => {
    setMostrarBusqueda(true);
    setBusquedaProducto('');
  };

  const handleSeleccionarProducto = async (productoId: number) => {
    try {
      const producto = await inventarioApi.getProducto(productoId);
      agregarProducto(producto);
      setMensaje('Producto agregado.');
    } catch (error) {
      setMensaje('No se pudo cargar el producto.');
    }
  };

  const handleActualizarCantidad = (id: number, cantidad: number) => {
    setCartItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, cantidad } : item))
    );
  };

  const handleActualizarDescuento = (id: number, descuento: number) => {
    setCartItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, descuentoPorcentaje: descuento } : item
      )
    );
  };

  const handleEliminarItem = (id: number) => {
    setCartItems((prev) => prev.filter((item) => item.id !== id));
  };

  const handleLimpiarTodo = () => {
    setCartItems([]);
    setDocumentoGenerado(null);
    setMensaje('Venta reiniciada.');
  };

  const handleSolicitarPermiso = () => {
    setMostrarPermiso(true);
  };

  const handleConfirmarPermiso = () => {
    if (!aprobadorId) {
      setMensaje('Selecciona un aprobador para habilitar el descuento.');
      return;
    }
    setDescuentoAutorizado(true);
    setMostrarPermiso(false);
    setMensaje('Permiso de descuento activo. El aprobador puede autorizar desde cualquier lugar.');
  };

  const handleGenerarDocumento = async (tipo: DocumentoGenerado['tipo']) => {
    if (!clienteId) {
      setMensaje('Selecciona un cliente para continuar.');
      return;
    }
    if (cartItems.length === 0) {
      setMensaje('Agrega productos antes de continuar.');
      return;
    }
    try {
      const venta = await ventasApi.crearVenta({
        tipo_comprobante: tipo,
        cliente: clienteId,
        vendedor: user?.id ?? 0,
        subtotal: totals.subtotal.toFixed(2),
        descuento_porcentaje: descuentoAutorizado ? descuentoGeneral : '0',
        descuento_valor: totals.descuentoTotal.toFixed(2),
        iva: totals.iva.toFixed(2),
        total: totals.total.toFixed(2),
        medio_pago: medioPago,
        efectivo_recibido: parseNumber(efectivoRecibido).toFixed(2),
        cambio: (parseNumber(efectivoRecibido) - totals.total).toFixed(2),
        detalles: cartItems.map((item) => {
          const subtotal = item.precioUnitario * item.cantidad;
          const descuento = subtotal * (item.descuentoPorcentaje / 100);
          const base = subtotal - descuento;
          const iva = base * (item.ivaPorcentaje / 100);
          const total = base + iva;
          return {
            producto: item.id,
            cantidad: item.cantidad,
            precio_unitario: item.precioUnitario.toFixed(2),
            descuento_unitario: descuento.toFixed(2),
            iva_porcentaje: item.ivaPorcentaje.toFixed(2),
            subtotal: subtotal.toFixed(2),
            total: total.toFixed(2),
          };
        }),
        descuento_aprobado_por: descuentoAutorizado ? Number(aprobadorId) : undefined,
      });
      const numeroComprobante =
        venta.numero_comprobante ||
        (tipo === 'FACTURA'
          ? `${configuracion?.prefijo_factura ?? ''} ${configuracion?.numero_factura ?? ''}`
          : tipo === 'REMISION'
            ? `${configuracion?.prefijo_remision ?? ''} ${configuracion?.numero_remision ?? ''}`
            : venta.numero_comprobante || 'COTIZACIÓN');

      setDocumentoGenerado({
        tipo,
        numero: numeroComprobante,
        cliente: clienteNombre,
        total: currencyFormatter.format(totals.total),
      });
      const detallesPreview: DocumentoDetalle[] = cartItems.map((item) => {
        const subtotalLinea = item.precioUnitario * item.cantidad;
        const descuentoLinea = subtotalLinea * (item.descuentoPorcentaje / 100);
        const base = subtotalLinea - descuentoLinea;
        const ivaLinea = base * (item.ivaPorcentaje / 100);
        const totalLinea = base + ivaLinea;
        return {
          descripcion: item.nombre,
          codigo: item.codigo,
          cantidad: item.cantidad,
          precioUnitario: item.precioUnitario,
          descuento: descuentoLinea,
          ivaPorcentaje: item.ivaPorcentaje,
          total: totalLinea,
        };
      });
      const medioPagoDisplay =
        {
          EFECTIVO: 'Efectivo',
          TARJETA: 'Tarjeta',
          TRANSFERENCIA: 'Transferencia',
          CREDITO: 'Crédito',
        }[medioPago] || medioPago;

      setDocumentoPreview({
        tipo,
        formato: 'POS',
        numero: numeroComprobante,
        fecha: new Date().toISOString(),
        clienteNombre,
        clienteDocumento: clienteDocumento || 'N/D',
        medioPago: medioPagoDisplay,
        estado: 'CONFIRMADA',
        detalles: detallesPreview,
        subtotal: totals.subtotal,
        descuento: totals.descuentoTotal,
        iva: totals.iva,
        total: totals.total,
        efectivoRecibido: parseNumber(efectivoRecibido),
        cambio,
      });
      setMensaje(`${venta.tipo_comprobante_display} generado correctamente.`);
    } catch (error) {
      setMensaje('No se pudo generar el documento. Revisa la conexión.');
    }
  };

  const cambio = useMemo(() => {
    const calculado = parseNumber(efectivoRecibido) - totals.total;
    return calculado >= 0 ? calculado : 0;
  }, [efectivoRecibido, totals.total]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Ventana de facturación</h1>
          <p className="text-sm text-slate-500">
            Genera cotizaciones, remisiones y facturas con lectura por código de barras o QR.
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
          <p className="font-semibold text-slate-700">Vendedor</p>
          <p className="text-slate-900">{user?.username ?? 'Usuario'}</p>
        </div>
      </div>

      <section className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-4">
        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase text-slate-500">Documento cliente</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={clienteDocumento}
              onChange={(event) => setClienteDocumento(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  handleBuscarCliente();
                }
              }}
              placeholder="Digite NIT/CC"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleBuscarCliente}
              className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-slate-600 transition hover:bg-slate-100"
            >
              <Search size={18} />
            </button>
          </div>
          <p className="text-sm font-semibold text-slate-800">{clienteNombre}</p>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase text-slate-500">Facturación</label>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {configuracion
              ? `${configuracion.prefijo_factura}-${configuracion.numero_factura}`
              : 'FAC-000000'}
          </div>
          <label className="text-xs font-semibold uppercase text-slate-500">Remisión</label>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {configuracion
              ? `${configuracion.prefijo_remision}-${configuracion.numero_remision}`
              : 'REM-000000'}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase text-slate-500">Medio de pago</label>
          <select
            value={medioPago}
            onChange={(event) =>
              setMedioPago(event.target.value as typeof medioPago)
            }
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="EFECTIVO">Efectivo</option>
            <option value="TARJETA">Tarjeta</option>
            <option value="TRANSFERENCIA">Transferencia</option>
            <option value="CREDITO">Crédito</option>
          </select>
          <label className="text-xs font-semibold uppercase text-slate-500">Efectivo recibido</label>
          <input
            type="text"
            value={efectivoRecibido}
            onChange={(event) => setEfectivoRecibido(event.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase text-slate-500">Lectura rápida</label>
          <div className="flex items-center gap-2">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <Barcode size={18} className="text-slate-500" />
              <input
                ref={codigoInputRef}
                type="text"
                value={codigoProducto}
                onChange={(event) => setCodigoProducto(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    handleBuscarProductoPorCodigo();
                  }
                }}
                placeholder="Digite código / QR / barra"
                className="w-full bg-transparent text-sm focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={handleBuscarProductoPorCodigo}
              className="rounded-lg bg-blue-600 p-2 text-white shadow-sm transition hover:bg-blue-700"
            >
              <PlusCircle size={18} />
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleAbrirBusqueda}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50"
            >
              <Search size={14} /> Consulta rápida
            </button>
            <button
              type="button"
              onClick={handleLimpiarTodo}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold uppercase text-rose-600 hover:bg-rose-50"
            >
              <Trash2 size={14} /> Borrar todo
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr,320px]">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 bg-yellow-50 px-4 py-2 text-xs font-semibold uppercase text-slate-600">
            Detalle de productos
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-yellow-400 text-xs uppercase text-slate-900">
                <tr>
                  <th className="px-3 py-2">Cant</th>
                  <th className="px-3 py-2">Código</th>
                  <th className="px-3 py-2">Artículo</th>
                  <th className="px-3 py-2 text-right">I.V.A.</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-right">Precio U</th>
                  <th className="px-3 py-2 text-right">Desc %</th>
                  <th className="px-3 py-2 text-right">Stock</th>
                  <th className="px-3 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {cartItems.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-3 py-10 text-center text-slate-500">
                      Agrega productos con lector o doble clic.
                    </td>
                  </tr>
                )}
                {cartItems.map((item) => {
                  const subtotal = item.precioUnitario * item.cantidad;
                  const descuento = subtotal * (item.descuentoPorcentaje / 100);
                  const base = subtotal - descuento;
                  const iva = base * (item.ivaPorcentaje / 100);
                  const total = base + iva;
                  return (
                    <tr key={item.id} className="border-b border-slate-100">
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() =>
                              handleActualizarCantidad(
                                item.id,
                                Math.max(1, item.cantidad - 1)
                              )
                            }
                            className="text-slate-400 hover:text-slate-600"
                          >
                            <MinusCircle size={16} />
                          </button>
                          <input
                            type="number"
                            min={1}
                            value={item.cantidad}
                            onChange={(event) =>
                              handleActualizarCantidad(
                                item.id,
                                Number(event.target.value || 1)
                              )
                            }
                            className="w-16 rounded border border-slate-200 px-2 py-1 text-center text-sm"
                          />
                          <button
                            type="button"
                            onClick={() =>
                              handleActualizarCantidad(item.id, item.cantidad + 1)
                            }
                            className="text-slate-400 hover:text-slate-600"
                          >
                            <PlusCircle size={16} />
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-slate-600">{item.codigo}</td>
                      <td className="px-3 py-2 font-medium text-slate-800">
                        {item.nombre}
                      </td>
                      <td className="px-3 py-2 text-right">{item.ivaPorcentaje}%</td>
                      <td className="px-3 py-2 text-right">
                        {currencyFormatter.format(total)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {currencyFormatter.format(item.precioUnitario)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={item.descuentoPorcentaje}
                          onChange={(event) =>
                            handleActualizarDescuento(
                              item.id,
                              Number(event.target.value || 0)
                            )
                          }
                          className="w-20 rounded border border-slate-200 px-2 py-1 text-right text-sm"
                          disabled={!descuentoAutorizado}
                        />
                      </td>
                      <td className="px-3 py-2 text-right">{item.stock}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => handleEliminarItem(item.id)}
                          className="rounded-lg border border-slate-200 p-2 text-rose-600 hover:bg-rose-50"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase text-slate-600">
                Totales
              </h2>
              <CircleDollarSign className="text-slate-400" size={20} />
            </div>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Subtotal</span>
                <span className="font-semibold text-slate-900">
                  {currencyFormatter.format(totals.subtotal)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Impuestos</span>
                <span className="font-semibold text-slate-900">
                  {currencyFormatter.format(totals.iva)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Descuentos</span>
                <span className="font-semibold text-rose-600">
                  -{currencyFormatter.format(totals.descuentoTotal)}
                </span>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-base font-semibold text-slate-900">
                Total a pagar: {currencyFormatter.format(totals.total)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Efectivo recibido</span>
                <span className="font-semibold text-emerald-600">
                  {currencyFormatter.format(parseNumber(efectivoRecibido))}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Cambio</span>
                <span className="font-semibold text-slate-900">
                  {currencyFormatter.format(cambio)}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase text-slate-600">
                Descuento general
              </h2>
              <ShieldCheck className="text-slate-400" size={20} />
            </div>
            <div className="mt-3 flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={100}
                value={descuentoGeneral}
                onChange={(event) => setDescuentoGeneral(event.target.value)}
                className="w-24 rounded-lg border border-slate-200 px-3 py-2 text-sm text-right"
                disabled={!descuentoAutorizado}
              />
              <span className="text-sm text-slate-500">% aplicado</span>
              <button
                type="button"
                onClick={handleSolicitarPermiso}
                className="ml-auto rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50"
              >
                Solicitar permiso
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              El descuento requiere autorización del dueño o persona designada.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold uppercase text-slate-600">
              Documentos
            </h2>
            <div className="mt-3 grid gap-2">
              <button
                type="button"
                onClick={() => handleGenerarDocumento('COTIZACION')}
                className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <span>Cotizar</span>
                <FileText size={18} />
              </button>
              <button
                type="button"
                onClick={() => handleGenerarDocumento('REMISION')}
                className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <span>Remisión</span>
                <FileText size={18} />
              </button>
              <button
                type="button"
                onClick={() => handleGenerarDocumento('FACTURA')}
                className="flex items-center justify-between rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
              >
                <span>Facturar</span>
                <FileText size={18} />
              </button>
            </div>
          </div>
        </div>
      </section>

      {mensaje && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {mensaje}
        </div>
      )}

      {documentoGenerado && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-900 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase text-emerald-600">Documento listo</p>
              <p className="text-lg font-semibold">
                {documentoGenerado.tipo} {documentoGenerado.numero}
              </p>
              <p className="text-sm text-emerald-700">
                Cliente: {documentoGenerado.cliente}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase text-emerald-600">Total</p>
              <p className="text-lg font-semibold">{documentoGenerado.total}</p>
            </div>
          </div>
          {documentoPreview ? (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-emerald-700">
              <button
                type="button"
                onClick={() =>
                  setDocumentoPreview((prev) =>
                    prev ? { ...prev, formato: 'POS' } : prev
                  )
                }
                className="rounded border border-emerald-300 px-3 py-1"
              >
                Ver POS
              </button>
              <button
                type="button"
                onClick={() =>
                  setDocumentoPreview((prev) =>
                    prev ? { ...prev, formato: 'CARTA' } : prev
                  )
                }
                className="rounded border border-emerald-300 px-3 py-1"
              >
                Ver carta
              </button>
              <button
                type="button"
                onClick={() => setDocumentoPreview(null)}
                className="rounded border border-emerald-300 px-3 py-1"
              >
                Cerrar vista
              </button>
            </div>
          ) : null}
        </div>
      )}

      {documentoPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4">
          <div className="relative w-full max-w-5xl rounded-lg bg-white p-6 shadow-xl">
            <button
              type="button"
              className="absolute right-4 top-4 text-slate-500 hover:text-slate-700"
              onClick={() => setDocumentoPreview(null)}
            >
              <X size={20} />
            </button>
            <div className="space-y-4">
              <div className="text-center">
                <p className="text-xs uppercase text-slate-500">Documento generado</p>
                <h3 className="text-lg font-semibold text-slate-800">
                  {documentoPreview.tipo} ({documentoPreview.formato})
                </h3>
              </div>
              <div className="max-h-[70vh] overflow-auto rounded border border-slate-200 bg-slate-50 p-4">
                <ComprobanteTemplate
                  formato={documentoPreview.formato}
                  tipo={documentoPreview.tipo}
                  numero={documentoPreview.numero}
                  fecha={documentoPreview.fecha}
                  clienteNombre={documentoPreview.clienteNombre}
                  clienteDocumento={documentoPreview.clienteDocumento}
                  medioPago={documentoPreview.medioPago}
                  estado={documentoPreview.estado}
                  detalles={documentoPreview.detalles}
                  subtotal={documentoPreview.subtotal}
                  descuento={documentoPreview.descuento}
                  iva={documentoPreview.iva}
                  total={documentoPreview.total}
                  efectivoRecibido={documentoPreview.efectivoRecibido}
                  cambio={documentoPreview.cambio}
                  notas={configuracion?.notas_factura}
                  resolucion={configuracion?.resolucion}
                  empresa={empresa}
                />
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setDocumentoPreview((prev) =>
                      prev ? { ...prev, formato: 'POS' } : prev
                    )
                  }
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600"
                >
                  POS
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setDocumentoPreview((prev) =>
                      prev ? { ...prev, formato: 'CARTA' } : prev
                    )
                  }
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600"
                >
                  Carta
                </button>
                <button
                  type="button"
                  onClick={() => setDocumentoPreview(null)}
                  className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
                >
                  Cerrar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {mostrarBusqueda && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-4xl rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <p className="text-xs font-semibold uppercase text-slate-500">
                  Listado de artículos
                </p>
                <h3 className="text-lg font-semibold text-slate-900">
                  Doble clic para añadir a la factura
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setMostrarBusqueda(false)}
                className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50"
              >
                <X size={18} />
              </button>
            </div>
            <div className="px-4 py-3">
              <div className="flex items-center gap-2">
                <Search size={18} className="text-slate-400" />
                <input
                  type="text"
                  value={busquedaProducto}
                  onChange={(event) => setBusquedaProducto(event.target.value)}
                  placeholder="Buscar por nombre o código..."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="max-h-[420px] overflow-auto px-4 pb-4">
              <table className="min-w-full text-left text-sm">
                <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Código</th>
                    <th className="px-3 py-2">Artículo</th>
                    <th className="px-3 py-2 text-right">Precio</th>
                    <th className="px-3 py-2 text-right">Stock</th>
                    <th className="px-3 py-2 text-right">Agregar</th>
                  </tr>
                </thead>
                <tbody>
                  {productos.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-3 py-6 text-center text-slate-500"
                      >
                        No hay resultados.
                      </td>
                    </tr>
                  )}
                  {productos.map((producto) => (
                    <tr
                      key={producto.id}
                      onDoubleClick={() => handleSeleccionarProducto(producto.id)}
                      className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="px-3 py-2 text-slate-600">{producto.codigo}</td>
                      <td className="px-3 py-2 font-medium text-slate-800">
                        {producto.nombre}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {currencyFormatter.format(Number(producto.precio_venta))}
                      </td>
                      <td className="px-3 py-2 text-right text-slate-600">
                        {producto.stock}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => handleSeleccionarProducto(producto.id)}
                          className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50"
                        >
                          Añadir
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {mostrarPermiso && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-slate-500">
                  Solicitud de permiso
                </p>
                <h3 className="text-lg font-semibold text-slate-900">
                  Autorización de descuento
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setMostrarPermiso(false)}
                className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50"
              >
                <X size={18} />
              </button>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Envía la solicitud al dueño o encargado desde cualquier lugar y selecciona
              su usuario cuando apruebe el descuento.
            </p>
            <div className="mt-4 space-y-3">
              <label className="text-xs font-semibold uppercase text-slate-500">
                Aprobador designado
              </label>
              <select
                value={aprobadorId}
                onChange={(event) => setAprobadorId(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <option value="">Seleccionar</option>
                {usuariosAprobadores.map((usuario) => (
                  <option key={usuario.id} value={usuario.id}>
                    {usuario.nombre}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleConfirmarPermiso}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                <ShieldCheck size={18} /> Confirmar permiso
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
