import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Barcode,
  CircleDollarSign,
  FileText,
  MinusCircle,
  PlusCircle,
  Search,
  ShieldCheck,
  Send,
  Trash2,
  X,
} from 'lucide-react';
import {
  inventarioApi,
  type Producto,
  type ProductoList,
} from '../api/inventario';
import {
  ventasApi,
  type DetalleVenta,
  type Venta,
  type VentaListItem,
} from '../api/ventas';
import { configuracionAPI } from '../api/configuracion';
import { useAuth } from '../contexts/AuthContext';
import { useNotification } from '../contexts/NotificationContext';
import ComprobanteTemplate, {
  type DocumentoDetalle,
} from '../components/ComprobanteTemplate';
import { descuentosApi, type SolicitudDescuento } from '../api/descuentos';
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
  unidadMedida: string;
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
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const parseNumber = (value: string) => {
  const normalized = value.replace(/[^\d.-]/g, '');
  const parsed = Number(normalized);
  return Number.isNaN(parsed) ? 0 : parsed;
};

const roundCop = (value: number) => Math.round(value);
const unidadPermiteDecimales = (unidadMedida?: string) =>
  Boolean(unidadMedida && unidadMedida !== 'N/A');

const getCantidadStep = (unidadMedida?: string) =>
  unidadPermiteDecimales(unidadMedida) ? 0.01 : 1;

const getCantidadMin = (unidadMedida?: string) =>
  unidadPermiteDecimales(unidadMedida) ? 0.01 : 1;

const normalizeCantidad = (cantidad: number, unidadMedida?: string) => {
  const min = getCantidadMin(unidadMedida);
  if (!Number.isFinite(cantidad)) {
    return min;
  }
  const clamped = Math.max(min, cantidad);
  if (unidadPermiteDecimales(unidadMedida)) {
    return Number(clamped.toFixed(2));
  }
  return Math.round(clamped);
};

const buildCartItemsFromDetalles = (detalles: DetalleVenta[]): CartItem[] =>
  detalles.map((detalle, index) => {
    const precioUnitario = Number(detalle.precio_unitario || 0);
    const descuentoUnitario = Number(detalle.descuento_unitario || 0);
    const descuentoPorcentaje =
      precioUnitario > 0
        ? Math.min(100, (descuentoUnitario / precioUnitario) * 100)
        : 0;
    return {
      id: detalle.producto || index,
      codigo: detalle.producto_codigo ?? '',
      nombre: detalle.producto_nombre ?? 'Producto',
      ivaPorcentaje: Number(detalle.iva_porcentaje || 0),
      precioUnitario,
      stock: 0,
      cantidad: Number(detalle.cantidad || 0),
      descuentoPorcentaje,
      unidadMedida: 'N/A',
    };
  });

export default function Ventas() {
  const { user } = useAuth();
  const { showNotification } = useNotification();
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
  const [aprobadorNombre, setAprobadorNombre] = useState('');
  const [estadoSolicitud, setEstadoSolicitud] = useState<SolicitudDescuento | null>(null);
  const [medioPago, setMedioPago] = useState<'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO'>('EFECTIVO');
  const [efectivoRecibido, setEfectivoRecibido] = useState('0');
  const [documentoGenerado, setDocumentoGenerado] = useState<DocumentoGenerado | null>(null);
  const [documentoPreview, setDocumentoPreview] = useState<DocumentoPreview | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [mostrarBusqueda, setMostrarBusqueda] = useState(false);
  const [productoInfo, setProductoInfo] = useState<ProductoList | Producto | null>(null);
  const [guardandoBorrador, setGuardandoBorrador] = useState(false);
  const [enviandoCaja, setEnviandoCaja] = useState(false);
  const [facturandoCaja, setFacturandoCaja] = useState(false);
  const [ventaBorrador, setVentaBorrador] = useState<Venta | null>(null);
  const [pendientesCaja, setPendientesCaja] = useState<VentaListItem[]>([]);
  const [cargandoPendientesCaja, setCargandoPendientesCaja] = useState(false);
  const [cargandoVentaCajaId, setCargandoVentaCajaId] = useState<number | null>(
    null
  );
  const [fechaCaja, setFechaCaja] = useState(
    () => new Date().toISOString().split('T')[0]
  );
  const [mostrarPermiso, setMostrarPermiso] = useState(false);
  const [usuariosAprobadores, setUsuariosAprobadores] = useState<{ id: number; nombre: string }[]>([]);
  const [cargandoAprobadores, setCargandoAprobadores] = useState(false);
  const [solicitudActivaId, setSolicitudActivaId] = useState<number | null>(null);
  const codigoInputRef = useRef<HTMLInputElement | null>(null);
  const lastSolicitudFetchRef = useRef(0);
  const esAdmin = useMemo(() => user?.role === 'ADMIN', [user?.role]);
  const esCaja = useMemo(() => Boolean(user?.es_cajero || esAdmin), [user?.es_cajero, esAdmin]);
  const ventaBloqueada = Boolean(
    ventaBorrador && ventaBorrador.estado !== 'BORRADOR' && !esCaja
  );

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
    if (!mostrarPermiso) return;
    const cached = window.localStorage.getItem('usuarios_aprobadores');
    if (cached && usuariosAprobadores.length === 0) {
      try {
        const parsed = JSON.parse(cached) as { id: number; nombre: string }[];
        if (Array.isArray(parsed)) {
          setUsuariosAprobadores(parsed);
        }
      } catch (error) {
        window.localStorage.removeItem('usuarios_aprobadores');
      }
    }
    if (usuariosAprobadores.length > 0) return;
    setCargandoAprobadores(true);
    configuracionAPI
      .obtenerAprobadores()
      .then((data) => {
        const lista = data.map((usuario) => ({
          id: usuario.id,
          nombre: `${usuario.first_name} ${usuario.last_name}`.trim() || usuario.username,
        }));
        setUsuariosAprobadores(lista);
        window.localStorage.setItem('usuarios_aprobadores', JSON.stringify(lista));
      })
      .catch(() => {
        setUsuariosAprobadores([]);
      })
      .finally(() => setCargandoAprobadores(false));
  }, [mostrarPermiso, usuariosAprobadores.length]);

  useEffect(() => {
    if (esAdmin) {
      setDescuentoAutorizado(true);
      setEstadoSolicitud(null);
      setMostrarPermiso(false);
    }
  }, [esAdmin]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      const hoy = new Date().toISOString().split('T')[0];
      setFechaCaja((prev) => (prev === hoy ? prev : hoy));
    }, 60000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!user?.id || esAdmin) return;
    if (!solicitudActivaId) {
      setEstadoSolicitud(null);
      setDescuentoAutorizado(false);
      return;
    }
    const actualizarEstadoSolicitud = async () => {
      const now = Date.now();
      if (now - lastSolicitudFetchRef.current < 2000) {
        return;
      }
      lastSolicitudFetchRef.current = now;
      try {
        const solicitudes = await descuentosApi.listarSolicitudes();
        const solicitud = solicitudes.find(
          (item) => item.id === solicitudActivaId
        );
        if (!solicitud) {
          setEstadoSolicitud(null);
          setDescuentoAutorizado(false);
          return;
        }
        setEstadoSolicitud(solicitud);
        const solicitado = Number(solicitud.descuento_solicitado || 0);
        if (solicitud.estado === 'APROBADO') {
          const aprobado = solicitud.descuento_aprobado
            ? Number(solicitud.descuento_aprobado)
            : solicitado;
          setDescuentoGeneral(String(aprobado));
          setDescuentoAutorizado(true);
        } else {
          setDescuentoGeneral(String(solicitado));
          setDescuentoAutorizado(false);
        }
      } catch (error) {
        setEstadoSolicitud(null);
      }
    };

    actualizarEstadoSolicitud();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        actualizarEstadoSolicitud();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    let intervalId: number | null = null;
    const startPolling = () => {
      if (intervalId !== null) return;
      intervalId = window.setInterval(() => {
        if (document.visibilityState === 'visible') {
          actualizarEstadoSolicitud();
        }
      }, 2000);
    };
    const stopPolling = () => {
      if (intervalId !== null) {
        window.clearInterval(intervalId);
        intervalId = null;
      }
    };

    if (estadoSolicitud?.estado === 'PENDIENTE') {
      startPolling();
    }

    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [esAdmin, estadoSolicitud?.estado, solicitudActivaId, user?.id]);

  const descuentoBloqueado =
    !esAdmin && estadoSolicitud?.estado === 'APROBADO';

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
          stock: Number(producto?.stock ?? 0),
          cantidad: repuesto.cantidad,
          descuentoPorcentaje: 0,
          unidadMedida: producto?.unidad_medida ?? 'N/A',
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
    const rawSubtotal = cartItems.reduce(
      (acc, item) => acc + item.precioUnitario * item.cantidad,
      0
    );
    const rawDescuentoLineas = cartItems.reduce((acc, item) => {
      const lineSubtotal = item.precioUnitario * item.cantidad;
      return acc + lineSubtotal * (item.descuentoPorcentaje / 100);
    }, 0);
    const rawDescuentoGeneralValor =
      rawSubtotal * (parseNumber(descuentoGeneral) / 100);
    const rawIva = cartItems.reduce((acc, item) => {
      const lineSubtotal = item.precioUnitario * item.cantidad;
      const lineDesc = lineSubtotal * (item.descuentoPorcentaje / 100);
      const base = lineSubtotal - lineDesc;
      return acc + base * (item.ivaPorcentaje / 100);
    }, 0);
    const subtotal = roundCop(rawSubtotal);
    const descuentoLineas = roundCop(rawDescuentoLineas);
    const descuentoGeneralValor = roundCop(rawDescuentoGeneralValor);
    const iva = roundCop(rawIva);
    const descuentoTotalPrevio = descuentoLineas + descuentoGeneralValor;
    const descuentoTotalAplicado =
      descuentoLineas +
      (descuentoAutorizado ? descuentoGeneralValor : 0);
    const totalPrevio = subtotal - descuentoTotalPrevio + iva;
    const totalAplicado = subtotal - descuentoTotalAplicado + iva;
    return {
      subtotal,
      descuentoTotalPrevio,
      descuentoTotalAplicado,
      descuentoGeneralValor,
      iva,
      totalPrevio,
      totalAplicado,
    };
  }, [cartItems, descuentoAutorizado, descuentoGeneral]);

  const cargarPendientesCaja = useCallback(() => {
    setCargandoPendientesCaja(true);
    ventasApi
      .getPendientesCaja()
      .then((data) => setPendientesCaja(data))
      .catch(() => setPendientesCaja([]))
      .finally(() => setCargandoPendientesCaja(false));
  }, []);

  useEffect(() => {
    if (!esCaja) {
      setPendientesCaja([]);
      return;
    }
    cargarPendientesCaja();
  }, [cargarPendientesCaja, esCaja]);

  const pendientesCajaHoy = useMemo(() => {
    return pendientesCaja.filter((venta) => {
      const fechaVenta = new Date(venta.fecha).toISOString().split('T')[0];
      return fechaVenta === fechaCaja;
    });
  }, [fechaCaja, pendientesCaja]);

  const handleCargarPendienteCaja = async (ventaId: number) => {
    if (ventaBloqueada || !esCaja) return;
    setCargandoVentaCajaId(ventaId);
    try {
      const venta = await ventasApi.getVenta(ventaId);
      setVentaBorrador(venta);
      setClienteId(venta.cliente);
      setClienteNombre(venta.cliente_info?.nombre ?? 'Cliente general');
      setClienteDocumento(venta.cliente_info?.numero_documento ?? '');
      setMedioPago(venta.medio_pago as typeof medioPago);
      setEfectivoRecibido(venta.efectivo_recibido ?? '0');
      setCartItems(buildCartItemsFromDetalles(venta.detalles || []));
      setDescuentoGeneral(venta.descuento_porcentaje ?? '0');
      setDescuentoAutorizado(true);
      setDocumentoGenerado(null);
      setDocumentoPreview(null);
      setEstadoSolicitud(null);
      setMostrarPermiso(false);
      setSolicitudActivaId(null);
      setMensaje('Venta cargada desde caja.');
    } catch (error) {
      setMensaje('No se pudo cargar la venta de caja.');
      showNotification({
        type: 'error',
        message: 'No se pudo cargar la venta de caja.',
      });
    } finally {
      setCargandoVentaCajaId(null);
    }
  };

  const handleFacturarEnCaja = async () => {
    if (!ventaBorrador || !esCaja) return;
    setFacturandoCaja(true);
    try {
      const facturada = await ventasApi.facturarEnCaja(ventaBorrador.id);
      resetVentaState();
      setMensaje('Venta facturada correctamente.');
      cargarPendientesCaja();
    } catch (error) {
      setMensaje('No se pudo facturar la venta. Revisa la conexión.');
    } finally {
      setFacturandoCaja(false);
    }
  };

  const handleBuscarCliente = async () => {
    if (ventaBloqueada) return;
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
    if (ventaBloqueada) return;
    setCartItems((prev) => {
      const existing = prev.find((item) => item.id === producto.id);
      if (existing) {
        return prev.map((item) =>
          item.id === producto.id
            ? {
                ...item,
                cantidad: normalizeCantidad(
                  item.cantidad + getCantidadStep(item.unidadMedida),
                  item.unidadMedida
                ),
              }
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
          stock: Number(producto.stock),
          cantidad: 1,
          descuentoPorcentaje: 0,
          unidadMedida: producto.unidad_medida ?? 'N/A',
        },
      ];
    });
  };

  const handleBuscarProductoPorCodigo = async () => {
    if (ventaBloqueada) return;
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
    if (ventaBloqueada) return;
    setMostrarBusqueda(true);
    setBusquedaProducto('');
    setProductoInfo(null);
  };

  const handleSeleccionarProducto = async (productoId: number) => {
    if (ventaBloqueada) return;
    try {
      const producto = await inventarioApi.getProducto(productoId);
      setProductoInfo(producto);
      agregarProducto(producto);
      setMensaje('Producto agregado.');
    } catch (error) {
      setMensaje('No se pudo cargar el producto.');
    }
  };

  const handleActualizarCantidad = (id: number, cantidad: number) => {
    if (ventaBloqueada) return;
    setCartItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              cantidad: normalizeCantidad(cantidad, item.unidadMedida),
            }
          : item
      )
    );
  };

  const handleActualizarDescuento = (id: number, descuento: number) => {
    if (ventaBloqueada) return;
    setCartItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, descuentoPorcentaje: descuento } : item
      )
    );
  };

  const handleEliminarItem = (id: number) => {
    if (ventaBloqueada) return;
    setCartItems((prev) => prev.filter((item) => item.id !== id));
  };

  const resetDescuentoState = () => {
    setDescuentoGeneral('0');
    setDescuentoAutorizado(esAdmin);
    setAprobadorId('');
    setAprobadorNombre('');
    setEstadoSolicitud(null);
    setMostrarPermiso(false);
    setSolicitudActivaId(null);
  };

  const resetVentaState = () => {
    setCartItems([]);
    setDocumentoGenerado(null);
    setDocumentoPreview(null);
    setVentaBorrador(null);
    setDetalleCaja(null);
    setClienteId(null);
    setClienteNombre('Cliente general');
    setClienteDocumento('');
    setMedioPago('EFECTIVO');
    setEfectivoRecibido('0');
    resetDescuentoState();
    setMensaje(null);
  };

  const handleLimpiarTodo = () => {
    if (ventaBloqueada) return;
    resetVentaState();
    setMensaje('Venta reiniciada.');
  };

  const handleSolicitarPermiso = () => {
    if (ventaBloqueada) return;
    if (esAdmin) {
      setMensaje('Los administradores no requieren permiso para aplicar descuentos.');
      return;
    }
    setMostrarPermiso(true);
  };

  const handleConfirmarPermiso = () => {
    if (ventaBloqueada) return;
    if (esAdmin) {
      setMostrarPermiso(false);
      setMensaje('Los administradores no requieren permiso para aplicar descuentos.');
      return;
    }
    if (!aprobadorId || !user?.id) {
      setMensaje('Selecciona un aprobador para habilitar el descuento.');
      return;
    }
    const aprobador = usuariosAprobadores.find(
      (usuario) => usuario.id === Number(aprobadorId)
    );
    const descuentoSolicitado = Number(descuentoGeneral || 0);
    descuentosApi
      .crearSolicitud({
        aprobador: Number(aprobadorId),
        descuento_solicitado: descuentoSolicitado,
        subtotal: totals.subtotal,
        iva: totals.iva,
        total_antes_descuento: totals.subtotal + totals.iva,
        total_con_descuento: totals.totalPrevio,
      })
      .then((nuevaSolicitud) => {
        setEstadoSolicitud(nuevaSolicitud);
        setSolicitudActivaId(nuevaSolicitud.id);
        setAprobadorNombre(aprobador?.nombre ?? 'Administrador');
        setDescuentoAutorizado(false);
        setMostrarPermiso(false);
        setMensaje('Solicitud enviada. El aprobador recibirá la notificación para autorizar.');
        showNotification({
          type: 'success',
          message: 'Solicitud de descuento enviada al aprobador.',
        });
      })
      .catch(() => {
        setMensaje('No se pudo enviar la solicitud. Revisa la conexión.');
        showNotification({
          type: 'error',
          message: 'No se pudo enviar la solicitud de descuento.',
        });
      });
  };

  const buildVentaPayload = (
    tipo: DocumentoGenerado['tipo'],
    vendedorId = ventaBorrador?.vendedor ?? user?.id ?? 0
  ) => {
    const efectivoRecibidoNumero = roundCop(parseNumber(efectivoRecibido));
    const cambioCalculado = Math.max(
      0,
      efectivoRecibidoNumero - totals.totalAplicado
    );
    return {
      tipo_comprobante: tipo,
      cliente: clienteId ?? 0,
      vendedor: vendedorId,
      subtotal: totals.subtotal.toFixed(2),
      descuento_porcentaje: descuentoAutorizado ? descuentoGeneral : '0',
      descuento_valor: totals.descuentoTotalAplicado.toFixed(2),
      iva: totals.iva.toFixed(2),
      total: totals.totalAplicado.toFixed(2),
      medio_pago: medioPago,
      efectivo_recibido: efectivoRecibidoNumero.toFixed(2),
      cambio: cambioCalculado.toFixed(2),
      detalles: cartItems.map((item) => {
        const subtotal = item.precioUnitario * item.cantidad;
        const descuento = subtotal * (item.descuentoPorcentaje / 100);
        const base = subtotal - descuento;
        const iva = base * (item.ivaPorcentaje / 100);
        const total = roundCop(base + iva);
        return {
          producto: item.id,
          cantidad: item.cantidad,
          precio_unitario: roundCop(item.precioUnitario).toFixed(2),
          descuento_unitario: roundCop(descuento).toFixed(2),
          iva_porcentaje: item.ivaPorcentaje.toFixed(2),
          subtotal: roundCop(subtotal).toFixed(2),
          total: total.toFixed(2),
        };
      }),
      descuento_aprobado_por:
        descuentoAutorizado && !esAdmin && aprobadorId
          ? Number(aprobadorId)
          : undefined,
    };
  };

  const validarVenta = () => {
    if (!clienteId) {
      setMensaje('Selecciona un cliente para continuar.');
      return false;
    }
    if (cartItems.length === 0) {
      setMensaje('Agrega productos antes de continuar.');
      return false;
    }
    if (!descuentoAutorizado && parseNumber(descuentoGeneral) > 0) {
      setMensaje('El descuento general está pendiente de aprobación.');
      return false;
    }
    return true;
  };

  const guardarBorrador = async () => {
    if (!validarVenta()) return null;
    const payload = buildVentaPayload('FACTURA');
    setGuardandoBorrador(true);
    try {
      const venta = ventaBorrador
        ? await ventasApi.actualizarVenta(ventaBorrador.id, payload)
        : await ventasApi.crearVenta(payload);
      setVentaBorrador(venta);
      setMensaje('Venta guardada como borrador.');
      return venta;
    } catch (error) {
      setMensaje('No se pudo guardar el borrador. Revisa la conexión.');
      return null;
    } finally {
      setGuardandoBorrador(false);
    }
  };

  const handleEnviarCaja = async () => {
    if (ventaBloqueada) return;
    let venta = ventaBorrador;
    if (!venta) {
      venta = await guardarBorrador();
    }
    if (!venta) return;
    setEnviandoCaja(true);
    try {
      const enviada = await ventasApi.enviarACaja(venta.id);
      setVentaBorrador(enviada);
      resetDescuentoState();
      setMensaje('Venta enviada a caja.');
      showNotification({
        type: 'success',
        message: 'Venta enviada a caja.',
      });
      cargarPendientesCaja();
    } catch (error) {
      setMensaje('No se pudo enviar a caja. Revisa la conexión.');
      showNotification({
        type: 'error',
        message: 'No se pudo enviar a caja.',
      });
    } finally {
      setEnviandoCaja(false);
    }
  };

  const handleFacturarDirecto = async () => {
    if (!validarVenta()) return;
    setGuardandoBorrador(true);
    try {
      const venta = await ventasApi.crearVenta({
        ...buildVentaPayload('FACTURA'),
        facturar_directo: true,
      });
      setVentaBorrador(venta);
      setDocumentoGenerado({
        tipo: 'FACTURA',
        numero: venta.numero_comprobante || `FAC-${venta.id}`,
        cliente: clienteNombre,
        total: currencyFormatter.format(totals.totalAplicado),
      });
      resetDescuentoState();
      setMensaje('Factura generada correctamente.');
    } catch (error) {
      setMensaje('No se pudo facturar. Revisa la conexión.');
    } finally {
      setGuardandoBorrador(false);
    }
  };

  const handleGenerarDocumento = async (tipo: DocumentoGenerado['tipo']) => {
    if (!validarVenta()) return;
    try {
      const efectivoRecibidoNumero = roundCop(parseNumber(efectivoRecibido));
      const cambioCalculado = Math.max(
        0,
        efectivoRecibidoNumero - totals.totalAplicado
      );
      const venta = await ventasApi.crearVenta(buildVentaPayload(tipo));
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
        total: currencyFormatter.format(totals.totalAplicado),
      });
      const detallesPreview: DocumentoDetalle[] = cartItems.map((item) => {
        const subtotalLinea = item.precioUnitario * item.cantidad;
        const descuentoLinea = subtotalLinea * (item.descuentoPorcentaje / 100);
        const base = subtotalLinea - descuentoLinea;
        const ivaLinea = base * (item.ivaPorcentaje / 100);
        const totalLinea = roundCop(base + ivaLinea);
        return {
          descripcion: item.nombre,
          codigo: item.codigo,
          cantidad: item.cantidad,
          precioUnitario: roundCop(item.precioUnitario),
          descuento: roundCop(descuentoLinea),
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
        estado: 'FACTURADA',
        detalles: detallesPreview,
        subtotal: totals.subtotal,
        descuento: totals.descuentoTotalAplicado,
        iva: totals.iva,
        total: totals.totalAplicado,
        efectivoRecibido: efectivoRecibidoNumero,
        cambio: roundCop(cambioCalculado),
      });
      resetDescuentoState();
      setMensaje(`${venta.tipo_comprobante_display} generado correctamente.`);
    } catch (error) {
      setMensaje('No se pudo generar el documento. Revisa la conexión.');
    }
  };

  const cambio = useMemo(() => {
    const calculado = roundCop(parseNumber(efectivoRecibido)) - totals.totalAplicado;
    return roundCop(calculado >= 0 ? calculado : 0);
  }, [efectivoRecibido, totals.totalAplicado]);

  const obtenerInfoProducto = (info: ProductoList | Producto | null) => {
    if (!info) return null;
    const nombre = 'producto_nombre' in info ? info.producto_nombre : info.nombre;
    const codigo = 'producto_codigo' in info ? info.producto_codigo : info.codigo;
    const precio = 'producto_precio' in info ? info.producto_precio : info.precio_venta;
    const stock = 'producto_stock' in info ? info.producto_stock : info.stock;
    return { nombre, codigo, precio, stock };
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-7">
          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Digite NIT/CC del cliente
            </label>
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
                disabled={ventaBloqueada}
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
              />
              <button
                type="button"
                onClick={handleBuscarCliente}
                disabled={ventaBloqueada}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
              >
                <Search size={18} />
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Cliente y/o razón social
            </label>
            <input
              type="text"
              value={clienteNombre}
              readOnly
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-800"
            />
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Vendedor
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-800">
              {user?.username ?? 'Usuario'}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Estado venta
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-semibold text-slate-800">
              {ventaBorrador?.estado
                ? {
                    BORRADOR: 'Borrador',
                    ENVIADA_A_CAJA: 'Enviada a caja',
                    FACTURADA: 'Facturada',
                    ANULADA: 'Anulada',
                  }[ventaBorrador.estado]
                : 'Nueva venta'}
            </div>
            {ventaBloqueada && (
              <button
                type="button"
                onClick={() => {
                  resetVentaState();
                }}
                className="text-xs font-semibold uppercase text-blue-600 hover:text-blue-700"
              >
                Iniciar nueva venta
              </button>
            )}
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Generar factura
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700">
              {configuracion
                ? `${configuracion.prefijo_factura}-${configuracion.numero_factura}`
                : 'FAC-000000'}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Generar remisión
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700">
              {configuracion
                ? `${configuracion.prefijo_remision}-${configuracion.numero_remision}`
                : 'REM-000000'}
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Medio de pago
            </label>
            <select
              value={medioPago}
              onChange={(event) =>
                setMedioPago(event.target.value as typeof medioPago)
              }
              disabled={ventaBloqueada}
              className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="EFECTIVO">Efectivo</option>
              <option value="TARJETA">Tarjeta</option>
              <option value="TRANSFERENCIA">Transferencia</option>
              <option value="CREDITO">Crédito</option>
            </select>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-12">
          <div className="space-y-2 lg:col-span-5">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Digite código de artículo
            </label>
            <div className="flex items-center gap-2">
              <div className="flex flex-1 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <Barcode size={18} className="text-slate-400" />
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
                  disabled={ventaBloqueada}
                  className="w-full bg-transparent text-sm focus:outline-none disabled:cursor-not-allowed"
                />
              </div>
              <button
                type="button"
                onClick={handleBuscarProductoPorCodigo}
                disabled={ventaBloqueada}
                className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                <PlusCircle size={18} />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleAbrirBusqueda}
                disabled={ventaBloqueada}
                className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
              >
                <Search size={14} /> Consulta rápida
              </button>
              <button
                type="button"
                onClick={handleLimpiarTodo}
                disabled={ventaBloqueada}
                className="flex items-center gap-2 rounded-xl border border-rose-200 px-3 py-1.5 text-[11px] font-semibold uppercase text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:bg-slate-100"
              >
                <Trash2 size={14} /> Borrar todo
              </button>
            </div>
          </div>

          <div className="space-y-2 lg:col-span-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Descuento general
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={100}
                value={descuentoGeneral}
                onChange={(event) => setDescuentoGeneral(event.target.value)}
                disabled={descuentoBloqueado || ventaBloqueada}
                className="w-20 rounded-lg border border-slate-200 px-2 py-1.5 text-sm text-right disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
              />
              <span className="text-sm text-slate-500">% aplicado</span>
            </div>
            {!esAdmin && (
              <button
                type="button"
                onClick={handleSolicitarPermiso}
                disabled={descuentoBloqueado || ventaBloqueada}
                className="rounded-xl border border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase text-slate-600 hover:bg-slate-50"
              >
                Solicitar permiso
              </button>
            )}
            {descuentoBloqueado && (
              <p className="text-xs text-slate-500">
                El descuento ya fue aprobado y no se puede modificar.
              </p>
            )}
          </div>

          <div className="space-y-2 lg:col-span-3">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Generar documento / caja
            </label>
            <div className="flex flex-wrap gap-2">
              {esCaja ? (
                <>
                  <button
                    type="button"
                    onClick={() => handleGenerarDocumento('COTIZACION')}
                    disabled={ventaBloqueada}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
                  >
                    <span>Cotizar</span>
                    <FileText size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleGenerarDocumento('REMISION')}
                    disabled={ventaBloqueada}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
                  >
                    <span>Remisión</span>
                    <FileText size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={
                      ventaBorrador?.estado === 'ENVIADA_A_CAJA'
                        ? handleFacturarEnCaja
                        : handleFacturarDirecto
                    }
                    disabled={
                      ventaBloqueada || guardandoBorrador || facturandoCaja
                    }
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-3 py-1.5 text-[11px] font-semibold uppercase text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    <span>
                      {guardandoBorrador || facturandoCaja
                        ? 'Facturando...'
                        : ventaBorrador?.estado === 'ENVIADA_A_CAJA'
                          ? 'Facturar en caja'
                          : 'Facturar'}
                    </span>
                    <FileText size={16} />
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => handleGenerarDocumento('COTIZACION')}
                    disabled={ventaBloqueada}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
                  >
                    <span>Cotizar</span>
                    <FileText size={16} />
                  </button>
                  <button
                    type="button"
                    onClick={handleEnviarCaja}
                    disabled={ventaBloqueada || enviandoCaja}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-1.5 text-[11px] font-semibold uppercase text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    <span>{enviandoCaja ? 'Enviando...' : 'Enviar a caja'}</span>
                    <Send size={16} />
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="space-y-2 lg:col-span-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Efectivo recibido
            </label>
          <input
            type="text"
            value={efectivoRecibido}
            onChange={(event) => setEfectivoRecibido(event.target.value)}
            disabled={ventaBloqueada}
            className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          />
            {!descuentoAutorizado && parseNumber(descuentoGeneral) > 0 && (
              <p className="text-xs text-amber-600">
                Descuento pendiente de aprobación.
              </p>
            )}
          </div>
        </div>

        {estadoSolicitud && (
          <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <p className="font-semibold text-slate-700">
              Estado: {estadoSolicitud.estado}
            </p>
            <p>
              Aprobador: {estadoSolicitud.aprobador_nombre || aprobadorNombre || 'Asignado'}
            </p>
            <p>
              Descuento solicitado: {estadoSolicitud.descuento_solicitado}%
              {estadoSolicitud.descuento_aprobado
                ? ` · Aprobado: ${estadoSolicitud.descuento_aprobado}%`
                : ''}
            </p>
          </div>
        )}
        {!esAdmin && (
          <p className="mt-2 text-xs text-slate-500">
            El descuento requiere autorización del dueño o persona designada.
          </p>
        )}
      </section>

      {mensaje && (
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {mensaje}
        </div>
      )}

      {esCaja && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">
                Caja
              </p>
              <h2 className="text-lg font-semibold text-slate-900">
                CAJA - Ventas pendientes por facturar
              </h2>
            </div>
            <button
              type="button"
              onClick={cargarPendientesCaja}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
            >
              Actualizar
            </button>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Documento</th>
                  <th className="px-3 py-2">Cliente</th>
                  <th className="px-3 py-2">Hora</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                {cargandoPendientesCaja && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                      Cargando pendientes...
                    </td>
                  </tr>
                )}
                {!cargandoPendientesCaja && pendientesCajaHoy.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                      No hay ventas pendientes.
                    </td>
                  </tr>
                )}
                {pendientesCajaHoy.map((venta) => (
                  <tr key={venta.id} className="border-b border-slate-100">
                    <td className="px-3 py-2 font-semibold text-slate-700">
                      {venta.numero_comprobante || `#${venta.id}`}
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {venta.cliente_nombre}
                    </td>
                    <td className="px-3 py-2 text-slate-500">
                      {new Date(venta.fecha).toLocaleTimeString('es-CO', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="px-3 py-2 text-right font-semibold text-slate-700">
                      {currencyFormatter.format(Number(venta.total))}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => handleCargarPendienteCaja(venta.id)}
                        disabled={cargandoVentaCajaId === venta.id}
                        className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
                      >
                        {cargandoVentaCajaId === venta.id
                          ? 'Cargando...'
                          : 'Cargar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 bg-yellow-50 px-5 py-2 text-xs font-semibold uppercase tracking-wide text-slate-700">
          Detalle de productos
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-yellow-400 text-[11px] uppercase text-slate-900">
              <tr>
                <th className="px-3 py-1.5">Cant</th>
                <th className="px-3 py-1.5">Código</th>
                <th className="px-3 py-1.5">Artículo</th>
                <th className="px-3 py-1.5 text-right">I.V.A.</th>
                <th className="px-3 py-1.5 text-right">Total</th>
                <th className="px-3 py-1.5 text-right">Precio U</th>
                <th className="px-3 py-1.5 text-right">Desc %</th>
                <th className="px-3 py-1.5 text-right">Stock</th>
                <th className="px-3 py-1.5 text-right">Acciones</th>
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
                const total = roundCop(base + iva);
                return (
                  <tr key={item.id} className="border-b border-slate-100">
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() =>
                            handleActualizarCantidad(
                              item.id,
                              item.cantidad - getCantidadStep(item.unidadMedida)
                            )
                          }
                          disabled={ventaBloqueada}
                          className="text-slate-400 hover:text-slate-600 disabled:cursor-not-allowed"
                        >
                          <MinusCircle size={16} />
                        </button>
                        <input
                          type="number"
                          min={getCantidadMin(item.unidadMedida)}
                          step={getCantidadStep(item.unidadMedida)}
                          value={item.cantidad}
                          onChange={(event) =>
                            handleActualizarCantidad(
                              item.id,
                              Number(event.target.value || 1)
                            )
                          }
                          disabled={ventaBloqueada}
                          className="w-14 rounded border border-slate-200 px-2 py-0.5 text-center text-sm disabled:cursor-not-allowed disabled:bg-slate-100"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            handleActualizarCantidad(
                              item.id,
                              item.cantidad + getCantidadStep(item.unidadMedida)
                            )
                          }
                          disabled={ventaBloqueada}
                          className="text-slate-400 hover:text-slate-600 disabled:cursor-not-allowed"
                        >
                          <PlusCircle size={16} />
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-1.5 text-slate-600">{item.codigo}</td>
                    <td className="px-3 py-1.5 font-medium text-slate-800">
                      {item.nombre}
                    </td>
                    <td className="px-3 py-1.5 text-right">{item.ivaPorcentaje}%</td>
                    <td className="px-3 py-1.5 text-right font-semibold text-slate-800">
                      {currencyFormatter.format(total)}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {currencyFormatter.format(item.precioUnitario)}
                    </td>
                    <td className="px-3 py-1.5 text-right">
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
                        className="w-16 rounded border border-slate-200 px-2 py-0.5 text-right text-sm disabled:cursor-not-allowed disabled:bg-slate-100"
                        disabled={!descuentoAutorizado || ventaBloqueada}
                      />
                    </td>
                    <td className="px-3 py-1.5 text-right">{item.stock}</td>
                    <td className="px-3 py-1.5 text-right">
                      <button
                        type="button"
                        onClick={() => handleEliminarItem(item.id)}
                        disabled={ventaBloqueada}
                        className="rounded-lg border border-slate-200 p-1.5 text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:bg-slate-100"
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
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
              Resumen de venta
            </h2>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Subtotal</span>
                <span className="text-base font-semibold text-slate-900">
                  {currencyFormatter.format(totals.subtotal)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Impuestos</span>
                <span className="text-base font-semibold text-slate-900">
                  {currencyFormatter.format(totals.iva)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Descuentos</span>
                <span className="text-base font-semibold text-rose-600">
                  -{currencyFormatter.format(totals.descuentoTotalPrevio)}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between rounded-xl bg-yellow-50 px-3 py-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
                Total a pagar
              </h2>
              <CircleDollarSign className="text-slate-400" size={20} />
            </div>
            <div className="mt-4 space-y-3 text-sm">
              <div className="rounded-xl border border-amber-200 bg-amber-100 px-4 py-3 text-lg font-semibold text-slate-900">
                {currencyFormatter.format(totals.totalAplicado)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Efectivo recibido</span>
                <span className="rounded-md bg-emerald-600 px-2 py-1 text-sm font-semibold text-white">
                  {currencyFormatter.format(roundCop(parseNumber(efectivoRecibido)))}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Cambio</span>
                <span className="rounded-md bg-blue-50 px-2 py-1 font-semibold text-blue-700">
                  {currencyFormatter.format(cambio)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

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
            <div className="grid gap-4 px-4 pb-4 lg:grid-cols-[260px,1fr]">
              <div className="rounded-xl border border-slate-100 bg-white px-3 py-3">
                <p className="text-xs font-semibold uppercase text-slate-500">
                  Consulta rápida
                </p>
                {(() => {
                  const info = obtenerInfoProducto(productoInfo);
                  if (!info) {
                    return (
                      <p className="mt-2 text-xs text-slate-400">
                        Selecciona un producto para ver precio y stock.
                      </p>
                    );
                  }
                  return (
                    <div className="mt-2 space-y-1 text-xs text-slate-600">
                      <p className="font-semibold text-slate-800">{info.nombre}</p>
                      <p>Código: {info.codigo}</p>
                      <p>Precio: {currencyFormatter.format(Number(info.precio))}</p>
                      <p>Stock: {info.stock}</p>
                    </div>
                  );
                })()}
              </div>
              <div className="max-h-[420px] overflow-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Código</th>
                      <th className="px-3 py-2">Artículo</th>
                      <th className="px-3 py-2 text-right">Precio</th>
                      <th className="px-3 py-2 text-right">Stock</th>
                      <th className="px-3 py-2 text-right">Acciones</th>
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
                        onClick={() => setProductoInfo(producto)}
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
              <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                <p className="font-semibold text-slate-700">
                  Descuento solicitado: {descuentoGeneral || 0}%
                </p>
                <p>Este valor quedará pendiente de aprobación.</p>
              </div>
              <label className="text-xs font-semibold uppercase text-slate-500">
                Aprobador designado
              </label>
              <select
                value={aprobadorId}
                onChange={(event) => {
                  const selectedId = event.target.value;
                  setAprobadorId(selectedId);
                  const selected = usuariosAprobadores.find(
                    (usuario) => usuario.id === Number(selectedId)
                  );
                  setAprobadorNombre(selected?.nombre ?? '');
                }}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                disabled={cargandoAprobadores || usuariosAprobadores.length === 0}
              >
                <option value="">
                  {cargandoAprobadores ? 'Cargando...' : 'Seleccionar'}
                </option>
                {usuariosAprobadores.map((usuario) => (
                  <option key={usuario.id} value={usuario.id}>
                    {usuario.nombre}
                  </option>
                ))}
              </select>
              {usuariosAprobadores.length === 0 && !cargandoAprobadores && (
                <p className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  No se encontraron aprobadores disponibles. Intenta nuevamente más tarde.
                </p>
              )}
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
