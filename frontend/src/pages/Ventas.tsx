import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Barcode,
  FileText,
  MinusCircle,
  PlusCircle,
  Printer,
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
  type Cliente,
  type FacturarCajaResponse,
  type Venta,
} from '../api/ventas';
import { configuracionAPI } from '../api/configuracion';
import { useAuth } from '../contexts/AuthContext';
import { useNotification } from '../contexts/NotificationContext';
import ComprobanteTemplate, {
  type DocumentoDetalle,
  type DocumentoFormato,
} from '../components/ComprobanteTemplate';
import { printComprobante } from '../utils/printComprobante';
import { descuentosApi, type SolicitudDescuento } from '../api/descuentos';
import type { ConfiguracionEmpresa } from '../types';
import type { ConfiguracionFacturacion } from '../types';
import {
  formatCurrencyCOP,
  formatMoneyCOP,
  parseMoneyCOP,
  roundCashCOP,
} from '../utils/moneyCOP';

type CartItem = {
  id: number;
  codigo: string;
  nombre: string;
  ivaPorcentaje: number;
  ivaExento: boolean;
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
  totalFiscal: number;
  totalCobro: number;
  efectivoRecibido: number;
  cambio: number;
  cufe?: string;
  qrUrl?: string;
  qrImageUrl?: string;
  referenceCode?: string;
  clienteDireccion?: string;
  clienteTelefono?: string;
  clienteEmail?: string;
  representacionGrafica?: string;
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

type CajaVentaPayload = {
  ventaId: number;
};

const buildDocumentoPreviewFromVenta = (
  venta: Venta,
  emision?: Partial<FacturarCajaResponse>
): DocumentoPreview => {
  const detallesPreview: DocumentoDetalle[] =
    venta.detalles?.map((detalle) => ({
      descripcion: detalle.producto_nombre ?? 'Producto',
      codigo: detalle.producto_codigo ?? '',
      cantidad: Number(detalle.cantidad),
      precioUnitario: parseMoneyCOP(detalle.precio_unitario),
      descuento: parseMoneyCOP(detalle.descuento_unitario),
      ivaPorcentaje: Number(detalle.iva_porcentaje),
      total: parseMoneyCOP(detalle.total),
    })) ?? [];

  return {
    tipo: venta.tipo_comprobante as DocumentoPreview['tipo'],
    numero: venta.numero_comprobante || `#${venta.id}`,
    fecha: venta.facturada_at || venta.fecha,
    clienteNombre: venta.cliente_info?.nombre ?? 'Cliente general',
    clienteDocumento: venta.cliente_info?.numero_documento ?? '',
    medioPago: venta.medio_pago_display || venta.medio_pago,
    estado: venta.estado_display || venta.estado,
    detalles: detallesPreview,
    subtotal: parseMoneyCOP(venta.subtotal),
    descuento: parseMoneyCOP(venta.descuento_valor),
    iva: parseMoneyCOP(venta.iva),
    totalFiscal: parseMoneyCOP(venta.total),
    totalCobro: parseMoneyCOP(venta.total),
    efectivoRecibido: parseMoneyCOP(venta.efectivo_recibido ?? 0),
    cambio: parseMoneyCOP(venta.cambio ?? 0),
    cufe:
      emision?.factura_electronica?.cufe ||
      emision?.cufe ||
      undefined,
    qrUrl:
      emision?.factura_lista?.public_url ||
      emision?.factura_lista?.qr_url ||
      emision?.pos_ticket?.qr_url ||
      undefined,
    qrImageUrl:
      emision?.factura_lista?.qr_image ||
      emision?.factura_lista?.factus_qr ||
      undefined,
    referenceCode:
      emision?.factura_lista?.reference_code ||
      emision?.reference_code ||
      undefined,
    clienteDireccion:
      venta.cliente_info?.direccion || '',
    clienteTelefono:
      venta.cliente_info?.telefono || '',
    clienteEmail:
      venta.cliente_info?.email || '',
    representacionGrafica:
      'Representación gráfica de factura electrónica de venta. Valide en DIAN con CUFE.',
  };
};
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

const roundDiv = (numerator: number, denominator: number) => {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator === 0) {
    return 0;
  }
  return Math.round(numerator / denominator);
};

const parsePercentToBasisPoints = (value: unknown) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.max(0, Math.round(value * 100));
  }
  const normalized = String(value ?? '')
    .replace(/[^\d,.-]/g, '')
    .replace(',', '.');
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.round(parsed * 100));
};

const isItemExento = (item: Pick<CartItem, 'ivaExento' | 'ivaPorcentaje'>) =>
  item.ivaExento || item.ivaPorcentaje <= 0;

const calcularLineaDesdePrecioFinal = (
  item: Pick<CartItem, 'precioUnitario' | 'cantidad' | 'descuentoPorcentaje' | 'ivaPorcentaje' | 'ivaExento'>
) => {
  const totalBrutoLinea = item.precioUnitario * item.cantidad;
  const descuentoLinea = roundDiv(
    totalBrutoLinea * parsePercentToBasisPoints(item.descuentoPorcentaje),
    10000
  );
  const totalNetoLinea = Math.max(0, totalBrutoLinea - descuentoLinea);

  if (isItemExento(item)) {
    return {
      totalBrutoLinea: Math.round(totalBrutoLinea),
      descuentoLinea: Math.round(descuentoLinea),
      totalNetoLinea: Math.round(totalNetoLinea),
      baseLinea: Math.round(totalNetoLinea),
      ivaLinea: 0,
    };
  }

  const ivaBasisPoints = parsePercentToBasisPoints(item.ivaPorcentaje);
  const baseLinea = roundDiv(totalNetoLinea * 10000, 10000 + ivaBasisPoints);
  const ivaLinea = totalNetoLinea - baseLinea;
  return {
    totalBrutoLinea: Math.round(totalBrutoLinea),
    descuentoLinea: Math.round(descuentoLinea),
    totalNetoLinea: Math.round(totalNetoLinea),
    baseLinea: Math.round(baseLinea),
    ivaLinea: Math.round(ivaLinea),
  };
};

export default function Ventas() {
  const MAX_EFECTIVO_DIGITOS = 13;
  const sanitizarEfectivoRecibido = (input: string): string =>
    input.replace(/\D/g, '').slice(0, MAX_EFECTIVO_DIGITOS);

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
  const [documentoFormato, setDocumentoFormato] = useState<DocumentoFormato>('POS');
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [mostrarBusqueda, setMostrarBusqueda] = useState(false);
  const [mostrarBusquedaClientes, setMostrarBusquedaClientes] = useState(false);
  const [busquedaClienteModal, setBusquedaClienteModal] = useState('');
  const [clientesBusqueda, setClientesBusqueda] = useState<Cliente[]>([]);
  const [cargandoClientesBusqueda, setCargandoClientesBusqueda] = useState(false);
  const [guardandoBorrador, setGuardandoBorrador] = useState(false);
  const [enviandoCaja, setEnviandoCaja] = useState(false);
  const [ventaBorrador, setVentaBorrador] = useState<Venta | null>(null);
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
    const state = location.state as { fromTaller?: TallerVentaPayload; fromCaja?: CajaVentaPayload } | null;
    return state?.fromTaller ?? null;
  }, [location.state]);
  const cajaPayload = useMemo(() => {
    const state = location.state as { fromTaller?: TallerVentaPayload; fromCaja?: CajaVentaPayload } | null;
    return state?.fromCaja ?? null;
  }, [location.state]);
  const inventarioYaAfectado = Boolean(tallerPayload?.ordenId);
  const redondeoCajaHabilitado = configuracion?.redondeo_caja_efectivo ?? true;
  const incrementoRedondeoCaja = configuracion?.redondeo_caja_incremento ?? 100;

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
    if (!mostrarBusquedaClientes) return;
    const timer = window.setTimeout(async () => {
      setCargandoClientesBusqueda(true);
      try {
        const response = await ventasApi.getClientes({
          search: busquedaClienteModal.trim() || undefined,
          is_active: true,
        });
        if (Array.isArray(response)) {
          setClientesBusqueda(response.slice(0, 25));
        } else {
          setClientesBusqueda((response.results ?? []).slice(0, 25));
        }
      } catch (error) {
        setClientesBusqueda([]);
      } finally {
        setCargandoClientesBusqueda(false);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [busquedaClienteModal, mostrarBusquedaClientes]);

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
    if (!user?.id || esAdmin) return;
    if (!solicitudActivaId) {
      setEstadoSolicitud(null);
      setDescuentoAutorizado(false);
      return;
    }
    const actualizarEstadoSolicitud = async () => {
      const now = Date.now();
      if (now - lastSolicitudFetchRef.current < 15000) {
        return;
      }
      lastSolicitudFetchRef.current = now;
      try {
        const solicitud = await descuentosApi.obtenerSolicitud(solicitudActivaId);
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
      }, 15000);
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
          ivaExento: Boolean(producto?.iva_exento),
          precioUnitario: parseMoneyCOP(
            repuesto.precioUnitario || producto?.precio_venta || 0
          ),
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

  const cargarVentaEnFormulario = (venta: Venta) => {
    const items: CartItem[] = (venta.detalles ?? []).map((detalle) => {
      const cantidad = Number(detalle.cantidad);
      const descuentoUnitario = Number(detalle.descuento_unitario);
      const precioFinal = Number(detalle.precio_unitario);
      const bruto = cantidad > 0 ? precioFinal * cantidad : 0;
      const descuentoLinea = descuentoUnitario * cantidad;
      const descuentoPorcentaje = bruto > 0 ? (descuentoLinea / bruto) * 100 : 0;

      return {
        id: detalle.producto,
        codigo: detalle.producto_codigo ?? '',
        nombre: detalle.producto_nombre ?? 'Producto',
        ivaPorcentaje: Number(detalle.iva_porcentaje),
        ivaExento: Number(detalle.iva_porcentaje) <= 0,
        precioUnitario: parseMoneyCOP(precioFinal),
        stock: Number(detalle.producto_stock ?? 0),
        cantidad: Number(cantidad.toFixed(2)),
        descuentoPorcentaje: Number.isFinite(descuentoPorcentaje) ? descuentoPorcentaje : 0,
        unidadMedida: 'N/A',
      };
    });

    setCartItems(items);
    setVentaBorrador(venta);
    setClienteId(venta.cliente_info?.id ?? venta.cliente ?? null);
    setClienteNombre(venta.cliente_info?.nombre ?? 'Cliente general');
    setClienteDocumento(venta.cliente_info?.numero_documento ?? '');
    setMedioPago((venta.medio_pago as 'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO') ?? 'EFECTIVO');
    setEfectivoRecibido(
      sanitizarEfectivoRecibido(String(parseMoneyCOP(venta.efectivo_recibido ?? 0)))
    );
    setDescuentoGeneral(String(Number(venta.descuento_porcentaje ?? 0)));
    setDescuentoAutorizado(true);
    setEstadoSolicitud(null);
    setSolicitudActivaId(null);
    setAprobadorId('');
    setAprobadorNombre('');
    setMostrarPermiso(false);
    setDocumentoGenerado(null);
    setDocumentoPreview(null);
    setMensaje(`Venta ${venta.numero_comprobante || `#${venta.id}`} cargada en caja. Revisa y confirma para facturar.`);
  };

  useEffect(() => {
    if (!cajaPayload?.ventaId || !esCaja) return;
    ventasApi
      .getDetalleCaja(cajaPayload.ventaId)
      .then((venta) => cargarVentaEnFormulario(venta))
      .catch((error) => {
        const detail = error instanceof Error ? error.message : 'No se pudo cargar la venta enviada a caja.';
        setMensaje(detail);
        showNotification({ type: 'error', message: detail });
      })
      .finally(() => {
        navigate('/ventas', { replace: true, state: null });
      });
  }, [cajaPayload?.ventaId, esCaja, navigate, showNotification]);

  const totals = useMemo(() => {
    const resumenLineas = cartItems.map(calcularLineaDesdePrecioFinal);
    const subtotal = resumenLineas.reduce((acc, line) => acc + line.baseLinea, 0);
    const iva = resumenLineas.reduce((acc, line) => acc + line.ivaLinea, 0);
    const totalLineas = resumenLineas.reduce((acc, line) => acc + line.totalNetoLinea, 0);
    const descuentoLineas = resumenLineas.reduce((acc, line) => acc + line.descuentoLinea, 0);
    const descuentoGeneralValor = roundDiv(
      totalLineas * parsePercentToBasisPoints(descuentoGeneral),
      10000
    );
    const descuentoTotalPrevio = descuentoLineas + descuentoGeneralValor;
    const descuentoTotalAplicado =
      descuentoLineas +
      (descuentoAutorizado ? descuentoGeneralValor : 0);
    const totalFiscal = totalLineas - (descuentoAutorizado ? descuentoGeneralValor : 0);
    const aplicaRedondeoCaja = medioPago === 'EFECTIVO' && redondeoCajaHabilitado;
    const totalCobro = aplicaRedondeoCaja
      ? roundCashCOP(totalFiscal, incrementoRedondeoCaja)
      : totalFiscal;
    return {
      subtotal,
      descuentoTotalPrevio,
      descuentoTotalAplicado,
      descuentoGeneralValor,
      iva,
      totalLineas,
      totalFiscal,
      totalCobro,
      aplicaRedondeoCaja,
    };
  }, [
    cartItems,
    descuentoAutorizado,
    descuentoGeneral,
    medioPago,
    redondeoCajaHabilitado,
    incrementoRedondeoCaja,
  ]);

  // Detectar si hay descuentos aplicados (para deshabilitar cotizaciones)
  const tieneDescuentosAplicados = useMemo(() => {
    const tieneDescuentoGeneral = parsePercentToBasisPoints(descuentoGeneral) > 0;
    const tieneDescuentoLineas = cartItems.some(
      (item) => item.descuentoPorcentaje > 0
    );
    return tieneDescuentoGeneral || tieneDescuentoLineas;
  }, [cartItems, descuentoGeneral]);
  const abrirModalBusquedaClientes = (textoInicial = '') => {
    if (ventaBloqueada) return;
    setMostrarBusquedaClientes(true);
    setBusquedaClienteModal(textoInicial);
  };

  const handleDocumentoClienteChange = (value: string) => {
    setClienteDocumento(value);
    if (!mostrarBusquedaClientes) {
      abrirModalBusquedaClientes(value);
      return;
    }
    setBusquedaClienteModal(value);
  };

  const handleSeleccionarCliente = (cliente: Cliente) => {
    setClienteId(cliente.id);
    setClienteDocumento(cliente.numero_documento ?? '');
    setClienteNombre(cliente.nombre ?? 'Cliente general');
    setMensaje(null);
    setMostrarBusquedaClientes(false);
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
          ivaExento: Boolean(producto.iva_exento),
          precioUnitario: parseMoneyCOP(producto.precio_venta),
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
  };

  const handleSeleccionarProducto = async (productoId: number) => {
    if (ventaBloqueada) return;
    try {
      const producto = await inventarioApi.getProducto(productoId);
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
        total_con_descuento: totals.totalFiscal,
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
    const efectivoRecibidoNumero = Number(efectivoRecibido || '0');
    const cambioCalculado = Math.max(0, efectivoRecibidoNumero - totals.totalCobro);
    const porcentajeDescuentoNormalizado = descuentoAutorizado
      ? (parsePercentToBasisPoints(descuentoGeneral) / 100).toFixed(2)
      : '0.00';
    const payloadBase = {
      tipo_comprobante: tipo,
      cliente: clienteId ?? 0,
      subtotal: String(totals.subtotal),
      descuento_porcentaje: porcentajeDescuentoNormalizado,
      descuento_valor: String(descuentoAutorizado ? totals.descuentoGeneralValor : 0),
      iva: String(totals.iva),
      total: String(totals.totalFiscal),
      medio_pago: medioPago,
      efectivo_recibido: String(efectivoRecibidoNumero),
      cambio: String(cambioCalculado),
      inventario_ya_afectado: inventarioYaAfectado,
      detalles: cartItems.map((item) => {
        const linea = calcularLineaDesdePrecioFinal(item);
        const descuentoUnitario = item.cantidad > 0 ? linea.descuentoLinea / item.cantidad : 0;
        return {
          producto: item.id,
          cantidad: item.cantidad,
          precio_unitario: String(item.precioUnitario),
          descuento_unitario: String(Math.round(descuentoUnitario)),
          iva_porcentaje: String(item.ivaPorcentaje),
          subtotal: String(linea.baseLinea),
          total: String(linea.totalNetoLinea),
        };
      }),
      descuento_aprobado_por:
        descuentoAutorizado && !esAdmin && aprobadorId
          ? Number(aprobadorId)
          : undefined,
    };
    if (vendedorId > 0) {
      return {
        ...payloadBase,
        vendedor: vendedorId,
      };
    }
    return payloadBase;
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
    if (!descuentoAutorizado && parsePercentToBasisPoints(descuentoGeneral) > 0) {
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
      const errorMessage =
        error instanceof Error ? error.message : 'No se pudo guardar el borrador. Revisa la conexión.';
      setMensaje(errorMessage);
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
      await ventasApi.enviarACaja(venta.id);
      resetVentaState();
      setMensaje('Venta enviada a caja.');
      showNotification({
        type: 'success',
        message: 'Venta enviada a caja.',
      });
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
      if (esCaja && ventaBorrador?.estado === 'ENVIADA_A_CAJA') {
        const ventaActualizada = await ventasApi.actualizarVenta(
          ventaBorrador.id,
          buildVentaPayload('FACTURA', ventaBorrador.vendedor)
        );
        const emision = await ventasApi.facturarEnCaja(ventaActualizada.id);
        const ventaFacturada = emision.venta ?? ventaActualizada;
        setVentaBorrador(ventaFacturada);
        setDocumentoGenerado({
          tipo: 'FACTURA',
          numero: emision.numero_factura || ventaFacturada.numero_comprobante || `FAC-${ventaFacturada.id}`,
          cliente: ventaFacturada.cliente_info?.nombre ?? clienteNombre,
          total: formatCurrencyCOP(ventaFacturada.total),
        });
        setDocumentoFormato('POS');
        setDocumentoPreview(buildDocumentoPreviewFromVenta(ventaFacturada, emision));
        setMensaje(
          emision.factus_sent
            ? `Factura electrónica emitida: ${emision.numero_factura} (${emision.estado_electronico || emision.status})`
            : emision.message || 'Factura local confirmada sin envío electrónico.'
        );
        showNotification({
          type: emision.factus_sent ? 'success' : 'error',
          message: emision.factus_sent
            ? `Emitida en Factus. CUFE: ${emision.cufe || 'N/D'} Ref: ${emision.reference_code || 'N/D'}`
            : emision.message || 'No se pudo confirmar emisión electrónica.',
        });
        return;
      }

      const venta = await ventasApi.crearVenta(buildVentaPayload('FACTURA'));
      const emision = await ventasApi.facturarVentaElectronica(venta.id);
      resetVentaState();
      setDocumentoGenerado({
        tipo: 'FACTURA',
        numero: emision.numero_factura || venta.numero_comprobante || `FAC-${venta.id}`,
        cliente: clienteNombre,
        total: formatCurrencyCOP(totals.totalCobro),
      });
      setDocumentoFormato('POS');
      setDocumentoPreview(buildDocumentoPreviewFromVenta(venta, emision));
      setMensaje(
        emision.factus_sent
          ? `Factura electrónica emitida: ${emision.numero_factura} (${emision.estado_electronico || emision.status})`
          : 'Factura local generada, pero sin confirmación de envío electrónico.'
      );
      showNotification({
        type: emision.factus_sent ? 'success' : 'error',
        message: emision.factus_sent
          ? `Emitida en Factus. CUFE: ${emision.cufe || 'N/D'} Ref: ${emision.reference_code || 'N/D'}`
          : emision.message || 'No se pudo confirmar emisión electrónica.',
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'No se pudo facturar. Revisa la conexión.';
      setMensaje(message);
      showNotification({
        type: 'error',
        message,
      });
    } finally {
      setGuardandoBorrador(false);
    }
  };

  const handleGenerarDocumento = async (tipo: DocumentoGenerado['tipo']) => {
    if (!validarVenta()) return;

    // Las cotizaciones NO pueden tener descuentos
    if (tipo === 'COTIZACION') {
      const tieneDescuentoGeneral = parsePercentToBasisPoints(descuentoGeneral) > 0;
      const tieneDescuentoLineas = cartItems.some(
        (item) => item.descuentoPorcentaje > 0
      );

      if (tieneDescuentoGeneral || tieneDescuentoLineas) {
        setMensaje(
          'Las cotizaciones no pueden tener descuentos. Si el cliente desea un descuento, ' +
            'debe realizar la compra directamente como remisión o factura.'
        );
        showNotification({
          type: 'error',
          message:
            'Las cotizaciones no permiten descuentos. Genere una remisión o factura si desea aplicar descuentos.',
        });
        return;
      }
    }

    try {
      const efectivoRecibidoNumero = Number(efectivoRecibido || '0');
      const cambioCalculado = Math.max(0, efectivoRecibidoNumero - totals.totalCobro);
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
        total: formatCurrencyCOP(totals.totalCobro),
      });
      const detallesPreview: DocumentoDetalle[] = cartItems.map((item) => {
        const linea = calcularLineaDesdePrecioFinal(item);
        return {
          descripcion: item.nombre,
          codigo: item.codigo,
          cantidad: item.cantidad,
          precioUnitario: item.precioUnitario,
          descuento: linea.descuentoLinea,
          ivaPorcentaje: item.ivaPorcentaje,
          total: linea.totalNetoLinea,
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
        totalFiscal: totals.totalFiscal,
        totalCobro: totals.totalCobro,
        efectivoRecibido: efectivoRecibidoNumero,
        cambio: cambioCalculado,
      });
      resetDescuentoState();
      setMensaje(`${venta.tipo_comprobante_display} generado correctamente.`);
    } catch (error) {
      setMensaje('No se pudo generar el documento. Revisa la conexión.');
    }
  };

  const cambio = useMemo(
    () => Math.max(Number(efectivoRecibido || '0') - totals.totalCobro, 0),
    [efectivoRecibido, totals.totalCobro]
  );

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
                onChange={(event) => handleDocumentoClienteChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    abrirModalBusquedaClientes(clienteDocumento);
                  }
                }}
                placeholder="Digite NIT/CC"
                disabled={ventaBloqueada}
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
              />
              <button
                type="button"
                onClick={() => abrirModalBusquedaClientes(clienteDocumento)}
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
                    disabled={ventaBloqueada || tieneDescuentosAplicados}
                    title={
                      tieneDescuentosAplicados
                        ? 'Las cotizaciones no permiten descuentos. Quite los descuentos o genere una remisión/factura.'
                        : undefined
                    }
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
                    onClick={handleFacturarDirecto}
                    disabled={ventaBloqueada || guardandoBorrador}
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-3 py-1.5 text-[11px] font-semibold uppercase text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    <span>
                      {guardandoBorrador ? 'Facturando...' : 'Facturar'}
                    </span>
                    <FileText size={16} />
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => handleGenerarDocumento('COTIZACION')}
                    disabled={ventaBloqueada || tieneDescuentosAplicados}
                    title={
                      tieneDescuentosAplicados
                        ? 'Las cotizaciones no permiten descuentos. Quite los descuentos o genere una remisión/factura.'
                        : undefined
                    }
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
            {tieneDescuentosAplicados && (
              <p className="mt-1 text-xs text-amber-600">
                Las cotizaciones no permiten descuentos. Si desea cotizar, quite los descuentos primero.
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
                <th className="px-3 py-1.5 text-right">Stock</th>
                <th className="px-3 py-1.5 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {cartItems.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-10 text-center text-slate-500">
                    Agrega productos con lector o doble clic.
                  </td>
                </tr>
              )}
              {cartItems.map((item) => {
                const linea = calcularLineaDesdePrecioFinal(item);
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
                      {formatCurrencyCOP(linea.totalNetoLinea)}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {formatCurrencyCOP(item.precioUnitario)}
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

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_minmax(360px,1.15fr)]">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
              Resumen de venta
            </h2>
            <div className="mt-4 space-y-3 text-sm sm:space-y-2.5">
              <div className="flex items-center justify-between gap-3 rounded-lg px-1 py-1">
                <span className="text-slate-500">Subtotal</span>
                <span className="text-base font-semibold tabular-nums text-slate-900">
                  {formatCurrencyCOP(totals.subtotal)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-lg px-1 py-1">
                <span className="text-slate-500">Impuestos</span>
                <span className="text-base font-semibold tabular-nums text-slate-900">
                  {formatCurrencyCOP(totals.iva)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3 rounded-lg px-1 py-1">
                <span className="text-slate-500">Descuentos</span>
                <span className="text-base font-semibold tabular-nums text-rose-600">
                  -{formatCurrencyCOP(totals.descuentoTotalAplicado)}
                </span>
              </div>
              <div className="mt-3 rounded-xl border border-amber-200/80 bg-amber-50 px-4 py-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold uppercase tracking-wide text-slate-700">
                    Total a pagar
                  </span>
                  <span className="text-3xl font-bold leading-none tabular-nums text-slate-900">
                    {formatCurrencyCOP(totals.totalCobro)}
                  </span>
                </div>
              </div>
              {!descuentoAutorizado && totals.descuentoTotalPrevio > totals.descuentoTotalAplicado && (
                <p className="text-xs text-amber-600">
                  Hay un descuento general pendiente de aprobación.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
              Cobro
            </h2>
            <div className="mt-4 grid gap-2.5">
              <div className="rounded-xl border border-emerald-200/90 bg-emerald-50/70 px-4 py-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                  <span className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                    Efectivo recibido
                  </span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={formatMoneyCOP(efectivoRecibido)}
                    onChange={(event) =>
                      setEfectivoRecibido(sanitizarEfectivoRecibido(event.target.value))
                    }
                    disabled={ventaBloqueada}
                    className="w-full rounded-lg border border-emerald-300 bg-white px-3.5 py-2 text-right text-2xl font-bold tabular-nums text-emerald-800 shadow-sm focus:border-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100 sm:max-w-[250px]"
                  />
                </div>
              </div>

              <div className="rounded-xl border border-blue-200/80 bg-blue-50/80 px-4 py-3">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                    Cambio
                  </span>
                  <span className="text-right text-2xl font-bold leading-none tabular-nums text-blue-800 sm:text-3xl">
                    {formatCurrencyCOP(cambio)}
                  </span>
                </div>
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
                  {documentoPreview.tipo}
                </h3>
              </div>
              <div className="flex justify-center gap-2">
                <button
                  type="button"
                  className={`rounded border px-3 py-1 text-xs font-semibold ${
                    documentoFormato === 'POS'
                      ? 'border-blue-600 bg-blue-600 text-white'
                      : 'border-slate-300 text-slate-700'
                  }`}
                  onClick={() => setDocumentoFormato('POS')}
                >
                  Formato POS
                </button>
                <button
                  type="button"
                  className={`rounded border px-3 py-1 text-xs font-semibold ${
                    documentoFormato === 'CARTA'
                      ? 'border-blue-600 bg-blue-600 text-white'
                      : 'border-slate-300 text-slate-700'
                  }`}
                  onClick={() => setDocumentoFormato('CARTA')}
                >
                  Formato Carta/A4
                </button>
              </div>
              <div className="max-h-[70vh] overflow-auto rounded border border-slate-200 bg-slate-50 p-4">
                <ComprobanteTemplate
                  formato={documentoFormato}
                  tipo={documentoPreview.tipo}
                  numero={documentoPreview.numero}
                  fecha={documentoPreview.fecha}
                  clienteNombre={documentoPreview.clienteNombre}
                  clienteDocumento={documentoPreview.clienteDocumento}
                  clienteDireccion={documentoPreview.clienteDireccion}
                  clienteTelefono={documentoPreview.clienteTelefono}
                  clienteEmail={documentoPreview.clienteEmail}
                  medioPago={documentoPreview.medioPago}
                  estado={documentoPreview.estado}
                  detalles={documentoPreview.detalles}
                  subtotal={documentoPreview.subtotal}
                  descuento={documentoPreview.descuento}
                  iva={documentoPreview.iva}
                  total={documentoPreview.totalFiscal}
                  efectivoRecibido={documentoPreview.efectivoRecibido}
                  cambio={documentoPreview.cambio}
                  notas={configuracion?.notas_factura}
                  resolucion={configuracion?.resolucion}
                  empresa={empresa}
                  cufe={documentoPreview.cufe}
                  qrUrl={documentoPreview.qrUrl}
                  qrImageUrl={documentoPreview.qrImageUrl}
                  referenceCode={documentoPreview.referenceCode}
                  representacionGrafica={documentoPreview.representacionGrafica}
                />
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (!documentoPreview) return;
                    printComprobante({
                      formato: documentoFormato,
                      tipo: documentoPreview.tipo,
                      numero: documentoPreview.numero,
                      fecha: documentoPreview.fecha,
                      clienteNombre: documentoPreview.clienteNombre,
                      clienteDocumento: documentoPreview.clienteDocumento,
                      clienteDireccion: documentoPreview.clienteDireccion,
                      clienteTelefono: documentoPreview.clienteTelefono,
                      clienteEmail: documentoPreview.clienteEmail,
                      medioPago: documentoPreview.medioPago,
                      estado: documentoPreview.estado,
                      detalles: documentoPreview.detalles,
                      subtotal: documentoPreview.subtotal,
                      descuento: documentoPreview.descuento,
                      iva: documentoPreview.iva,
                      total: documentoPreview.totalFiscal,
                      efectivoRecibido: documentoPreview.efectivoRecibido,
                      cambio: documentoPreview.cambio,
                      notas: configuracion?.notas_factura,
                      resolucion: configuracion?.resolucion,
                      empresa,
                      cufe: documentoPreview.cufe,
                      qrUrl: documentoPreview.qrUrl,
                      qrImageUrl: documentoPreview.qrImageUrl,
                      referenceCode: documentoPreview.referenceCode,
                      representacionGrafica: documentoPreview.representacionGrafica,
                    });
                  }}
                  className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
                >
                  <Printer size={16} />
                  Imprimir
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
            <div className="px-4 pb-4">
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
                        className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                      >
                        <td className="px-3 py-2 text-slate-600">{producto.codigo}</td>
                        <td className="px-3 py-2 font-medium text-slate-800">
                          {producto.nombre}
                        </td>
                        <td className="px-3 py-2 text-right text-slate-600">
                          {formatCurrencyCOP(producto.precio_venta)}
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

      {mostrarBusquedaClientes && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-4xl rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <p className="text-xs font-semibold uppercase text-slate-500">
                  Búsqueda de clientes
                </p>
                <h3 className="text-lg font-semibold text-slate-900">
                  Buscar por NIT/CC o razón social
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setMostrarBusquedaClientes(false)}
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
                  value={busquedaClienteModal}
                  onChange={(event) => {
                    const value = event.target.value;
                    setBusquedaClienteModal(value);
                    setClienteDocumento(value);
                  }}
                  placeholder="Buscar cliente por NIT/CC o nombre..."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="px-4 pb-4">
              <div className="max-h-[380px] overflow-auto rounded-xl border border-slate-100">
                <table className="min-w-full text-left text-sm">
                  <thead className="sticky top-0 bg-slate-100 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">NIT/CC</th>
                      <th className="px-3 py-2">Nombre / Razón social</th>
                      <th className="px-3 py-2">Teléfono</th>
                      <th className="px-3 py-2 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cargandoClientesBusqueda && (
                      <tr>
                        <td colSpan={4} className="px-3 py-4 text-center text-slate-500">
                          Buscando clientes...
                        </td>
                      </tr>
                    )}
                    {!cargandoClientesBusqueda && clientesBusqueda.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-slate-500">
                          No hay clientes para la búsqueda actual.
                        </td>
                      </tr>
                    )}
                    {!cargandoClientesBusqueda &&
                      clientesBusqueda.map((cliente) => (
                        <tr
                          key={cliente.id}
                          onDoubleClick={() => handleSeleccionarCliente(cliente)}
                          className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                        >
                          <td className="px-3 py-2 text-slate-600">{cliente.numero_documento}</td>
                          <td className="px-3 py-2 font-medium text-slate-800">{cliente.nombre}</td>
                          <td className="px-3 py-2 text-slate-600">
                            {cliente.telefono || '—'}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <button
                              type="button"
                              onClick={() => handleSeleccionarCliente(cliente)}
                              className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-semibold uppercase text-slate-600 hover:bg-slate-50"
                            >
                              Seleccionar
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
