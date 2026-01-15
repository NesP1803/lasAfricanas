import { useMemo, useState } from 'react';
import { inventarioApi, type Producto, type ProductoList } from '../api/inventario';
import { ventasApi } from '../api/ventas';
import { usuariosApi } from '../api/usuarios';
import { useAuth } from '../contexts/AuthContext';
import type { Cliente } from '../api/ventas';

type VentaItem = {
  producto: Producto;
  cantidad: number;
};

const currency = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 2,
});

const toNumber = (value: string | number) => Number(value || 0);
const CLIENTE_DEFECTO = {
  documento: '0000000000',
  nombre: 'Cliente General',
};

export default function PuntoVenta() {
  const { user } = useAuth();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [buscarCliente, setBuscarCliente] = useState('');
  const [codigoScan, setCodigoScan] = useState('');
  const [busquedaProducto, setBusquedaProducto] = useState('');
  const [productosEncontrados, setProductosEncontrados] = useState<ProductoList[]>([]);
  const [cargandoProductos, setCargandoProductos] = useState(false);
  const [ventaItems, setVentaItems] = useState<VentaItem[]>([]);
  const [mostrarBuscador, setMostrarBuscador] = useState(false);
  const [mensaje, setMensaje] = useState('');
  const [descuentoPorcentaje, setDescuentoPorcentaje] = useState('0');
  const [descuentoAprobador, setDescuentoAprobador] = useState<
    { id: number; nombre: string } | null
  >(null);
  const [mostrarAprobacion, setMostrarAprobacion] = useState(false);
  const [aprobacionUsuario, setAprobacionUsuario] = useState('');
  const [aprobacionPassword, setAprobacionPassword] = useState('');
  const [aprobacionError, setAprobacionError] = useState('');
  const [medioPago, setMedioPago] = useState<'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO'>('EFECTIVO');
  const [efectivoRecibido, setEfectivoRecibido] = useState('0');
  const [observaciones, setObservaciones] = useState('');
  const [filtroRapido, setFiltroRapido] = useState('');

  const descuentoNumero = Number(descuentoPorcentaje) || 0;

  const itemsFiltrados = useMemo(() => {
    if (!filtroRapido.trim()) return ventaItems;
    const filtro = filtroRapido.toLowerCase();
    return ventaItems.filter((item) =>
      `${item.producto.codigo} ${item.producto.nombre}`.toLowerCase().includes(filtro)
    );
  }, [filtroRapido, ventaItems]);

  const totales = useMemo(() => {
    let subtotal = 0;
    let iva = 0;
    let descuentoValor = 0;

    ventaItems.forEach((item) => {
      const precio = toNumber(item.producto.precio_venta);
      const descuentoUnitario = (precio * descuentoNumero) / 100;
      const base = (precio - descuentoUnitario) * item.cantidad;
      const ivaLinea = (base * toNumber(item.producto.iva_porcentaje)) / 100;
      subtotal += base;
      iva += ivaLinea;
      descuentoValor += descuentoUnitario * item.cantidad;
    });

    const total = subtotal + iva;
    return { subtotal, iva, descuentoValor, total };
  }, [ventaItems, descuentoNumero]);

  const cambio = useMemo(() => {
    return Math.max(0, Number(efectivoRecibido) - totales.total);
  }, [efectivoRecibido, totales.total]);

  const buscarClientePorDocumento = async () => {
    if (!buscarCliente.trim()) return;

    try {
      const clienteEncontrado = await ventasApi.buscarCliente(buscarCliente.trim());
      setCliente(clienteEncontrado);
      setMensaje('Cliente cargado correctamente.');
    } catch (error) {
      setMensaje('Cliente no encontrado.');
    }
  };

  const obtenerClientePorDefecto = async () => {
    try {
      const clienteEncontrado = await ventasApi.buscarCliente(CLIENTE_DEFECTO.documento);
      setCliente(clienteEncontrado);
      return clienteEncontrado;
    } catch (error) {
      try {
        const nuevoCliente = await ventasApi.crearCliente({
          tipo_documento: 'CC',
          numero_documento: CLIENTE_DEFECTO.documento,
          nombre: CLIENTE_DEFECTO.nombre,
          telefono: '',
          email: '',
          direccion: '',
          ciudad: '',
        });
        setCliente(nuevoCliente);
        return nuevoCliente;
      } catch (createError) {
        setMensaje('No se pudo crear el cliente general.');
        return null;
      }
    }
  };

  const abrirBuscador = () => {
    setMostrarBuscador(true);
    setProductosEncontrados([]);
    setBusquedaProducto('');
  };

  const buscarProductos = async () => {
    if (!busquedaProducto.trim()) return;
    setCargandoProductos(true);
    try {
      const data = await inventarioApi.getProductos({ search: busquedaProducto });
      setProductosEncontrados(data.results || []);
    } catch (error) {
      setMensaje('No se pudieron cargar los productos.');
    } finally {
      setCargandoProductos(false);
    }
  };

  const agregarProducto = (producto: Producto) => {
    setVentaItems((prev) => {
      const existente = prev.find((item) => item.producto.id === producto.id);
      if (existente) {
        return prev.map((item) =>
          item.producto.id === producto.id
            ? { ...item, cantidad: item.cantidad + 1 }
            : item
        );
      }
      return [...prev, { producto, cantidad: 1 }];
    });
    setMensaje(`Producto agregado: ${producto.nombre}`);
  };

  const agregarProductoPorCodigo = async () => {
    if (!codigoScan.trim()) return;

    try {
      const producto = await inventarioApi.buscarPorCodigo(codigoScan.trim());
      agregarProducto(producto);
      setCodigoScan('');
    } catch (error) {
      setMensaje('Producto no encontrado con ese código.');
    }
  };

  const agregarProductoPorLista = async (productoList: ProductoList) => {
    try {
      const producto = await inventarioApi.getProducto(productoList.id);
      agregarProducto(producto);
      setMostrarBuscador(false);
    } catch (error) {
      setMensaje('No se pudo cargar el producto seleccionado.');
    }
  };

  const actualizarCantidad = (productoId: number, cantidad: number) => {
    if (cantidad <= 0) return;
    setVentaItems((prev) =>
      prev.map((item) =>
        item.producto.id === productoId ? { ...item, cantidad } : item
      )
    );
  };

  const quitarProducto = (productoId: number) => {
    setVentaItems((prev) => prev.filter((item) => item.producto.id !== productoId));
  };

  const limpiarVenta = () => {
    setVentaItems([]);
    setDescuentoPorcentaje('0');
    setDescuentoAprobador(null);
    setMensaje('Venta reiniciada.');
  };

  const solicitarAprobacion = () => {
    if (descuentoNumero <= 0) return;
    setMostrarAprobacion(true);
    setAprobacionError('');
  };

  const confirmarAprobacion = async () => {
    try {
      const data = await usuariosApi.validarDescuento({
        username: aprobacionUsuario,
        password: aprobacionPassword,
        descuento_porcentaje: descuentoNumero,
      });
      setDescuentoAprobador({ id: data.id, nombre: data.nombre });
      setMostrarAprobacion(false);
      setAprobacionPassword('');
      setAprobacionUsuario('');
      setMensaje(`Descuento aprobado por ${data.nombre}.`);
    } catch (error) {
      setAprobacionError((error as Error).message);
    }
  };

  const aplicarDescuento = (value: string) => {
    setDescuentoPorcentaje(value);
    setDescuentoAprobador(null);
  };

  const crearVenta = async (tipo: 'COTIZACION' | 'REMISION' | 'FACTURA') => {
    if (ventaItems.length === 0) {
      setMensaje('Agrega productos antes de continuar.');
      return;
    }
    if (descuentoNumero > 0 && !descuentoAprobador) {
      setMensaje('El descuento requiere aprobación antes de continuar.');
      setMostrarAprobacion(true);
      return;
    }

    try {
      const clienteSeleccionado = cliente || (await obtenerClientePorDefecto());
      if (!clienteSeleccionado) return;

      const detalles = ventaItems.map((item) => {
        const precio = toNumber(item.producto.precio_venta);
        const descuentoUnitario = (precio * descuentoNumero) / 100;
        const subtotal = (precio - descuentoUnitario) * item.cantidad;
        const ivaLinea = (subtotal * toNumber(item.producto.iva_porcentaje)) / 100;
        const totalLinea = subtotal + ivaLinea;

        return {
          producto: item.producto.id,
          cantidad: item.cantidad,
          precio_unitario: precio.toFixed(2),
          descuento_unitario: descuentoUnitario.toFixed(2),
          iva_porcentaje: toNumber(item.producto.iva_porcentaje).toFixed(2),
          subtotal: subtotal.toFixed(2),
          total: totalLinea.toFixed(2),
        };
      });

      await ventasApi.crearVenta({
        tipo_comprobante: tipo,
        cliente: clienteSeleccionado.id,
        vendedor: user?.id || 0,
        subtotal: totales.subtotal.toFixed(2),
        descuento_porcentaje: descuentoNumero.toFixed(2),
        descuento_valor: totales.descuentoValor.toFixed(2),
        iva: totales.iva.toFixed(2),
        total: totales.total.toFixed(2),
        medio_pago: medioPago,
        efectivo_recibido: Number(efectivoRecibido).toFixed(2),
        cambio: cambio.toFixed(2),
        observaciones,
        detalles,
        descuento_aprobado_por: descuentoAprobador?.id,
      });

      setMensaje(`${tipo} registrada correctamente.`);
      limpiarVenta();
      setObservaciones('');
    } catch (error) {
      setMensaje('No se pudo registrar la venta.');
    }
  };

  return (
    <div className="h-full flex flex-col bg-slate-100">
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white p-4 flex flex-wrap items-center justify-between gap-4 shadow">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="text-xs font-semibold block mb-1">DIGITE Nº/CC DEL CLIENTE</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Número de documento"
                value={buscarCliente}
                onChange={(e) => setBuscarCliente(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && buscarClientePorDocumento()}
                className="px-3 py-2 rounded border border-slate-200 text-slate-900 w-48 focus:outline-none focus:ring-2 focus:ring-amber-300"
              />
              <button
                onClick={buscarClientePorDocumento}
                className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-slate-900 rounded font-bold shadow-sm"
              >
                ✓
              </button>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold block mb-1">CLIENTE / RAZÓN SOCIAL</label>
            <div className="bg-white/90 text-slate-900 px-4 py-2 rounded-xl min-w-[240px] shadow-sm border border-white/40">
              <p className="font-semibold text-lg">
                {cliente?.nombre || 'Cliente general'}
              </p>
              <p className="text-sm text-slate-500">
                {cliente?.numero_documento || 'Sin documento'}
              </p>
            </div>
          </div>
        </div>

        <div className="text-right">
          <p className="text-xs text-slate-200">VENDEDOR</p>
          <p className="font-semibold text-lg">{user?.username?.toUpperCase() || '---'}</p>
          <p className="text-xs text-slate-300">{new Date().toLocaleString('es-CO')}</p>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-4 p-4">
        <section className="bg-white rounded-2xl shadow-lg border border-slate-200 flex flex-col">
          <div className="border-b border-slate-100 p-4 flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-[220px]">
              <label className="text-xs font-semibold text-slate-500 block mb-1">
                ESCÁNER / CÓDIGO DEL ARTÍCULO
              </label>
              <input
                type="text"
                placeholder="Escanea código de barras, QR o escribe el código"
                value={codigoScan}
                onChange={(e) => setCodigoScan(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && agregarProductoPorCodigo()}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-300"
              />
            </div>

            <button
              onClick={agregarProductoPorCodigo}
              className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 shadow-sm"
            >
              Añadir producto
            </button>

            <button
              onClick={abrirBuscador}
              className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100"
            >
              Buscar en catálogo
            </button>

            <button
              onClick={limpiarVenta}
              className="px-4 py-2 bg-rose-50 text-rose-600 border border-rose-200 rounded-lg hover:bg-rose-100"
            >
              Borrar todo
            </button>
          </div>

          <div className="overflow-auto flex-1">
            <table className="min-w-full text-sm">
              <thead className="bg-amber-100 text-slate-700 uppercase text-xs">
                <tr>
                  <th className="px-3 py-2 text-left">Cant</th>
                  <th className="px-3 py-2 text-left">Código</th>
                  <th className="px-3 py-2 text-left">Artículo</th>
                  <th className="px-3 py-2 text-right">IVA</th>
                  <th className="px-3 py-2 text-right">Precio U</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {itemsFiltrados.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                      No hay productos agregados.
                    </td>
                  </tr>
                ) : (
                  itemsFiltrados.map((item) => {
                    const precio = toNumber(item.producto.precio_venta);
                    const descuentoUnitario = (precio * descuentoNumero) / 100;
                    const subtotal = (precio - descuentoUnitario) * item.cantidad;
                    const ivaLinea = (subtotal * toNumber(item.producto.iva_porcentaje)) / 100;
                    const totalLinea = subtotal + ivaLinea;

                    return (
                      <tr
                        key={item.producto.id}
                        className="border-b border-slate-100 hover:bg-amber-50/40"
                      >
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            min={1}
                            value={item.cantidad}
                            onChange={(e) =>
                              actualizarCantidad(item.producto.id, Number(e.target.value))
                            }
                            className="w-16 px-2 py-1 border border-slate-200 rounded-md"
                          />
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-500">
                          {item.producto.codigo}
                        </td>
                        <td className="px-3 py-2">
                          <p className="font-medium text-slate-800">{item.producto.nombre}</p>
                          <p className="text-xs text-slate-400">{item.producto.categoria_nombre}</p>
                        </td>
                        <td className="px-3 py-2 text-right">
                          {item.producto.iva_porcentaje}%
                        </td>
                        <td className="px-3 py-2 text-right">
                          {currency.format(precio)}
                        </td>
                        <td className="px-3 py-2 text-right font-semibold">
                          {currency.format(totalLinea)}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <button
                            onClick={() => quitarProducto(item.producto.id)}
                            className="text-rose-500 hover:text-rose-700"
                          >
                            Quitar
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="border-t border-slate-100 p-4 flex flex-wrap items-center justify-between gap-3 bg-slate-50/70">
            <div className="flex items-center gap-3">
              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1">BÚSQUEDA RÁPIDA</label>
                <input
                  type="text"
                  placeholder="Filtrar por código o nombre"
                  value={filtroRapido}
                  onChange={(e) => setFiltroRapido(e.target.value)}
                  className="px-3 py-2 border border-slate-200 rounded-md"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1">OBSERVACIONES</label>
                <input
                  type="text"
                  value={observaciones}
                  onChange={(e) => setObservaciones(e.target.value)}
                  placeholder="Observaciones para la venta"
                  className="px-3 py-2 border border-slate-200 rounded-md w-64"
                />
              </div>
            </div>
            <p className="text-xs text-slate-400">{mensaje}</p>
          </div>
        </section>

        <aside className="bg-white rounded-2xl shadow-lg border border-slate-200 p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-800">Resumen</h2>
            {descuentoNumero > 0 && (
              <span className={`text-xs px-2 py-1 rounded-full ${descuentoAprobador ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                {descuentoAprobador
                  ? `Aprobado por ${descuentoAprobador.nombre}`
                  : 'Descuento pendiente de aprobación'}
              </span>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Subtotal</span>
              <span className="font-semibold">{currency.format(totales.subtotal)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Impuestos</span>
              <span className="font-semibold">{currency.format(totales.iva)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Descuentos</span>
              <span className="font-semibold text-rose-600">
                -{currency.format(totales.descuentoValor)}
              </span>
            </div>
            <div className="flex items-center justify-between text-base">
              <span className="font-semibold">Total a pagar</span>
              <span className="font-bold text-slate-900">{currency.format(totales.total)}</span>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-500 block mb-1">Descuento general (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                value={descuentoPorcentaje}
                onChange={(e) => aplicarDescuento(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md"
              />
            </div>
            {descuentoNumero > 0 && !descuentoAprobador && (
              <button
                onClick={solicitarAprobacion}
                className="w-full px-3 py-2 bg-amber-400 text-slate-900 rounded-md hover:bg-amber-300"
              >
                Solicitar aprobación
              </button>
            )}
            <div>
              <label className="text-xs font-semibold text-slate-500 block mb-1">Medio de pago</label>
              <select
                value={medioPago}
                onChange={(e) => setMedioPago(e.target.value as typeof medioPago)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md"
              >
                <option value="EFECTIVO">Efectivo</option>
                <option value="TARJETA">Tarjeta</option>
                <option value="TRANSFERENCIA">Transferencia</option>
                <option value="CREDITO">Crédito</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500 block mb-1">Efectivo recibido</label>
              <input
                type="number"
                min={0}
                value={efectivoRecibido}
                onChange={(e) => setEfectivoRecibido(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-md"
              />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Cambio</span>
              <span className="font-semibold text-emerald-600">
                {currency.format(cambio)}
              </span>
            </div>
          </div>

          <div className="mt-auto space-y-2">
            <button
              onClick={() => crearVenta('COTIZACION')}
              className="w-full px-3 py-3 bg-slate-100 border border-slate-200 rounded-lg hover:bg-slate-200"
            >
              Cotizar
            </button>
            <button
              onClick={() => crearVenta('REMISION')}
              className="w-full px-3 py-3 bg-slate-900 text-white rounded-lg hover:bg-slate-800"
            >
              Remisión
            </button>
            <button
              onClick={() => crearVenta('FACTURA')}
              className="w-full px-3 py-3 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600"
            >
              Facturar
            </button>
          </div>
        </aside>
      </div>

      {mostrarBuscador && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl">
            <div className="border-b border-slate-100 p-4 flex items-center justify-between">
              <h3 className="font-semibold text-slate-800">Listado de artículos</h3>
              <button
                onClick={() => setMostrarBuscador(false)}
                className="text-slate-500 hover:text-slate-700"
              >
                Cerrar
              </button>
            </div>
            <div className="p-4 flex items-center gap-3">
              <input
                type="text"
                placeholder="Buscar por nombre o código"
                value={busquedaProducto}
                onChange={(e) => setBusquedaProducto(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && buscarProductos()}
                className="flex-1 px-3 py-2 border border-slate-200 rounded-lg"
              />
              <button
                onClick={buscarProductos}
                className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800"
              >
                Buscar
              </button>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-amber-100 text-slate-700 uppercase text-xs">
                  <tr>
                    <th className="px-3 py-2 text-left">Código</th>
                    <th className="px-3 py-2 text-left">Artículo</th>
                    <th className="px-3 py-2 text-right">Precio</th>
                    <th className="px-3 py-2 text-right">Stock</th>
                  </tr>
                </thead>
                <tbody>
                  {cargandoProductos ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                        Buscando productos...
                      </td>
                    </tr>
                  ) : productosEncontrados.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-slate-400">
                        Ingresa un criterio para buscar artículos.
                      </td>
                    </tr>
                  ) : (
                    productosEncontrados.map((producto) => (
                      <tr
                        key={producto.id}
                        onDoubleClick={() => agregarProductoPorLista(producto)}
                        className="border-b border-slate-100 hover:bg-amber-50/40 cursor-pointer"
                      >
                        <td className="px-3 py-2 font-mono text-xs text-slate-500">
                          {producto.codigo}
                        </td>
                        <td className="px-3 py-2">
                          <p className="font-medium text-slate-800">{producto.nombre}</p>
                          <p className="text-xs text-slate-400">{producto.categoria_nombre}</p>
                        </td>
                        <td className="px-3 py-2 text-right">{currency.format(Number(producto.precio_venta))}</td>
                        <td className="px-3 py-2 text-right">{producto.stock}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="border-t border-slate-100 px-4 py-3 text-xs text-slate-400">
              Doble clic sobre un artículo para añadirlo a la factura.
            </div>
          </div>
        </div>
      )}

      {mostrarAprobacion && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="font-semibold text-slate-800">Aprobación de descuento</h3>
            <p className="text-sm text-slate-500">
              El descuento de {descuentoNumero}% requiere aprobación del dueño o persona designada.
            </p>
            <div>
              <label className="text-xs font-semibold text-slate-500 block mb-1">Usuario autorizado</label>
              <input
                type="text"
                value={aprobacionUsuario}
                onChange={(e) => setAprobacionUsuario(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500 block mb-1">Contraseña</label>
              <input
                type="password"
                value={aprobacionPassword}
                onChange={(e) => setAprobacionPassword(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded"
              />
            </div>
            {aprobacionError && (
              <p className="text-sm text-red-500">{aprobacionError}</p>
            )}
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setMostrarAprobacion(false)}
                className="px-3 py-2 border border-slate-200 rounded"
              >
                Cancelar
              </button>
              <button
                onClick={confirmarAprobacion}
                className="px-3 py-2 bg-slate-900 text-white rounded"
              >
                Autorizar descuento
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
