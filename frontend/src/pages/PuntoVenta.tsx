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
    if (!cliente) {
      setMensaje('Debes seleccionar un cliente para continuar.');
      return;
    }
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
        cliente: cliente.id,
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
    <div className="h-full flex flex-col bg-gray-100">
      <div className="bg-gradient-to-r from-blue-700 to-blue-600 text-white p-5 flex flex-wrap items-center justify-between gap-4 shadow-lg border-b-4 border-blue-800">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="text-xs font-bold block mb-2 tracking-wide uppercase">Digite Nº/CC del Cliente</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Número de documento"
                value={buscarCliente}
                onChange={(e) => setBuscarCliente(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && buscarClientePorDocumento()}
                className="px-4 py-2.5 rounded-lg text-gray-900 w-52 font-semibold shadow-sm focus:ring-2 focus:ring-blue-300 focus:outline-none"
              />
              <button
                onClick={buscarClientePorDocumento}
                className="px-5 py-2.5 bg-green-500 hover:bg-green-600 rounded-lg font-bold shadow-md hover:shadow-lg transition-all text-lg"
              >
                ✓
              </button>
            </div>
          </div>

          <div>
            <label className="text-xs font-bold block mb-2 tracking-wide uppercase">Cliente / Razón Social</label>
            <div className="bg-white text-gray-900 px-5 py-2.5 rounded-lg min-w-[280px] shadow-sm border-2 border-blue-200">
              <p className="font-bold text-xl text-blue-900">
                {cliente?.nombre || 'Cliente general'}
              </p>
              <p className="text-sm text-gray-600 font-medium">
                {cliente?.numero_documento || 'Sin documento'}
              </p>
            </div>
          </div>
        </div>

        <div className="text-right bg-blue-800/30 px-6 py-3 rounded-lg border border-blue-500/30">
          <p className="text-xs text-blue-200 font-bold uppercase tracking-wide">Vendedor</p>
          <p className="font-bold text-xl text-white">{user?.username?.toUpperCase() || 'ADMIN'}</p>
          <p className="text-xs text-blue-200 font-medium">{new Date().toLocaleString('es-CO')}</p>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px] gap-4 p-4">
        <section className="bg-white rounded-xl shadow-lg border border-gray-200 flex flex-col overflow-hidden">
          <div className="bg-gradient-to-r from-slate-100 to-gray-100 border-b-2 border-gray-300 p-4 flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[240px]">
              <label className="text-xs font-bold text-gray-700 block mb-2 uppercase tracking-wide">
                Escáner / Código del Artículo
              </label>
              <input
                type="text"
                placeholder="Escanea código de barras, QR o escribe el código"
                value={codigoScan}
                onChange={(e) => setCodigoScan(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && agregarProductoPorCodigo()}
                className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-blue-400 font-medium shadow-sm"
              />
            </div>

            <button
              onClick={agregarProductoPorCodigo}
              className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide"
            >
              Añadir producto
            </button>

            <button
              onClick={abrirBuscador}
              className="px-5 py-2.5 bg-white border-2 border-gray-300 rounded-lg hover:bg-gray-50 font-bold shadow-sm hover:shadow-md transition-all uppercase tracking-wide"
            >
              Buscar en catálogo
            </button>

            <button
              onClick={limpiarVenta}
              className="px-5 py-2.5 bg-red-500 text-white border-2 border-red-600 rounded-lg hover:bg-red-600 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide"
            >
              Borrar todo
            </button>
          </div>

          <div className="overflow-auto flex-1">
            <table className="min-w-full text-sm">
              <thead className="bg-gradient-to-r from-blue-600 to-blue-700 text-white uppercase text-xs font-bold sticky top-0 shadow-md">
                <tr>
                  <th className="px-4 py-3 text-left border-r border-blue-500">Cant</th>
                  <th className="px-4 py-3 text-left border-r border-blue-500">Código</th>
                  <th className="px-4 py-3 text-left border-r border-blue-500">Artículo</th>
                  <th className="px-4 py-3 text-right border-r border-blue-500">IVA</th>
                  <th className="px-4 py-3 text-right border-r border-blue-500">Precio U</th>
                  <th className="px-4 py-3 text-right border-r border-blue-500">Total</th>
                  <th className="px-4 py-3 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="bg-white">
                {itemsFiltrados.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-gray-400 text-base">
                      <div className="flex flex-col items-center gap-2">
                        <svg className="w-16 h-16 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                        <span className="font-semibold">No hay productos agregados.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  itemsFiltrados.map((item, index) => {
                    const precio = toNumber(item.producto.precio_venta);
                    const descuentoUnitario = (precio * descuentoNumero) / 100;
                    const subtotal = (precio - descuentoUnitario) * item.cantidad;
                    const ivaLinea = (subtotal * toNumber(item.producto.iva_porcentaje)) / 100;
                    const totalLinea = subtotal + ivaLinea;

                    return (
                      <tr
                        key={item.producto.id}
                        className={`border-b border-gray-200 hover:bg-blue-50 transition-colors ${index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}`}
                      >
                        <td className="px-4 py-3">
                          <input
                            type="number"
                            min={1}
                            value={item.cantidad}
                            onChange={(e) =>
                              actualizarCantidad(item.producto.id, Number(e.target.value))
                            }
                            className="w-16 px-3 py-1.5 border-2 border-gray-300 rounded-md text-center font-bold text-base focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
                          />
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-blue-600 font-semibold">
                          {item.producto.codigo}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-bold text-gray-800 text-base">{item.producto.nombre}</p>
                          <p className="text-xs text-gray-500 font-medium">{item.producto.categoria_nombre}</p>
                        </td>
                        <td className="px-4 py-3 text-right font-semibold text-gray-700">
                          {item.producto.iva_porcentaje}%
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-gray-800 text-base">
                          {currency.format(precio)}
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-blue-700 text-lg">
                          {currency.format(totalLinea)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => quitarProducto(item.producto.id)}
                            className="px-3 py-1.5 text-red-600 hover:text-white hover:bg-red-600 border border-red-600 rounded-md font-bold transition-all text-xs uppercase"
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

          <div className="bg-gradient-to-r from-slate-100 to-gray-100 border-t-2 border-gray-300 p-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1.5 uppercase tracking-wide">Búsqueda Rápida</label>
                <input
                  type="text"
                  placeholder="Filtrar por código o nombre"
                  value={filtroRapido}
                  onChange={(e) => setFiltroRapido(e.target.value)}
                  className="px-3 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 shadow-sm"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1.5 uppercase tracking-wide">Observaciones</label>
                <input
                  type="text"
                  value={observaciones}
                  onChange={(e) => setObservaciones(e.target.value)}
                  placeholder="Observaciones para la venta"
                  className="px-3 py-2 border-2 border-gray-300 rounded-lg w-64 focus:ring-2 focus:ring-blue-400 focus:border-blue-400 shadow-sm"
                />
              </div>
            </div>
            {mensaje && (
              <div className="bg-blue-100 border-l-4 border-blue-600 px-4 py-2 rounded-r-lg">
                <p className="text-sm text-blue-800 font-semibold">{mensaje}</p>
              </div>
            )}
          </div>
        </section>

        <aside className="bg-white rounded-xl shadow-xl border-2 border-gray-200 flex flex-col overflow-hidden">
          <div className="bg-gradient-to-r from-blue-700 to-blue-600 text-white px-5 py-4 border-b-4 border-blue-800">
            <h2 className="font-bold text-xl uppercase tracking-wide">Resumen</h2>
            {descuentoNumero > 0 && (
              <span className={`inline-block mt-2 text-xs px-3 py-1.5 rounded-full font-bold ${descuentoAprobador ? 'bg-green-500 text-white' : 'bg-yellow-400 text-yellow-900'}`}>
                {descuentoAprobador
                  ? `✓ Aprobado por ${descuentoAprobador.nombre}`
                  : '⚠ Descuento pendiente de aprobación'}
              </span>
            )}
          </div>

          <div className="p-5 space-y-3 bg-gradient-to-b from-gray-50 to-white">
            <div className="flex items-center justify-between py-2 border-b border-gray-200">
              <span className="text-gray-600 font-semibold uppercase text-sm">Subtotal</span>
              <span className="font-bold text-lg text-gray-800">{currency.format(totales.subtotal)}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-200">
              <span className="text-gray-600 font-semibold uppercase text-sm">Impuestos</span>
              <span className="font-bold text-lg text-gray-800">{currency.format(totales.iva)}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-200">
              <span className="text-gray-600 font-semibold uppercase text-sm">Descuentos</span>
              <span className="font-bold text-lg text-red-600">
                -{currency.format(totales.descuentoValor)}
              </span>
            </div>
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-4 rounded-lg shadow-md mt-4">
              <div className="flex items-center justify-between">
                <span className="font-bold uppercase text-sm tracking-wide">Total a pagar</span>
                <span className="font-bold text-3xl">{currency.format(totales.total)}</span>
              </div>
            </div>
          </div>

          <div className="border-t-2 border-gray-200 bg-white p-5 space-y-3">
            <div>
              <label className="text-xs font-bold text-gray-700 block mb-2 uppercase tracking-wide">Descuento general (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                value={descuentoPorcentaje}
                onChange={(e) => aplicarDescuento(e.target.value)}
                className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg text-lg font-bold text-center focus:ring-2 focus:ring-blue-400 focus:border-blue-400 shadow-sm"
              />
            </div>
            {descuentoNumero > 0 && !descuentoAprobador && (
              <button
                onClick={solicitarAprobacion}
                className="w-full px-4 py-3 bg-yellow-500 text-yellow-900 rounded-lg hover:bg-yellow-600 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide border-2 border-yellow-600"
              >
                ⚠ Solicitar aprobación
              </button>
            )}
            <div>
              <label className="text-xs font-bold text-gray-700 block mb-2 uppercase tracking-wide">Medio de pago</label>
              <select
                value={medioPago}
                onChange={(e) => setMedioPago(e.target.value as typeof medioPago)}
                className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg text-base font-semibold focus:ring-2 focus:ring-blue-400 focus:border-blue-400 shadow-sm"
              >
                <option value="EFECTIVO">💵 Efectivo</option>
                <option value="TARJETA">💳 Tarjeta</option>
                <option value="TRANSFERENCIA">🏦 Transferencia</option>
                <option value="CREDITO">📋 Crédito</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-bold text-gray-700 block mb-2 uppercase tracking-wide">Efectivo recibido</label>
              <input
                type="number"
                min={0}
                value={efectivoRecibido}
                onChange={(e) => setEfectivoRecibido(e.target.value)}
                className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg text-lg font-bold text-center focus:ring-2 focus:ring-blue-400 focus:border-blue-400 shadow-sm"
              />
            </div>
            <div className="bg-green-100 border-2 border-green-500 p-3 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-green-800 font-bold uppercase text-sm">Cambio</span>
                <span className="font-bold text-2xl text-green-700">
                  {currency.format(cambio)}
                </span>
              </div>
            </div>
          </div>

          <div className="p-5 space-y-3 bg-gradient-to-b from-white to-gray-50">
            <button
              onClick={() => crearVenta('COTIZACION')}
              className="w-full px-4 py-3.5 bg-white border-2 border-gray-400 text-gray-700 rounded-lg hover:bg-gray-50 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide text-base"
            >
              📋 Cotizar
            </button>
            <button
              onClick={() => crearVenta('REMISION')}
              className="w-full px-4 py-3.5 bg-blue-600 text-white border-2 border-blue-700 rounded-lg hover:bg-blue-700 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide text-base"
            >
              📄 Remisión
            </button>
            <button
              onClick={() => crearVenta('FACTURA')}
              className="w-full px-4 py-4 bg-gradient-to-r from-green-500 to-green-600 text-white border-2 border-green-700 rounded-lg hover:from-green-600 hover:to-green-700 font-bold shadow-lg hover:shadow-xl transition-all uppercase tracking-wide text-lg"
            >
              ✓ Facturar
            </button>
          </div>
        </aside>
      </div>

      {mostrarBuscador && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-4xl overflow-hidden border-2 border-gray-300">
            <div className="bg-gradient-to-r from-blue-700 to-blue-600 text-white px-6 py-4 flex items-center justify-between border-b-4 border-blue-800">
              <h3 className="font-bold text-xl uppercase tracking-wide">Listado de Artículos</h3>
              <button
                onClick={() => setMostrarBuscador(false)}
                className="text-white hover:text-red-300 hover:bg-red-600/30 px-3 py-1.5 rounded-lg font-bold transition-all"
              >
                ✕ Cerrar
              </button>
            </div>
            <div className="bg-gray-50 p-4 flex items-center gap-3 border-b-2 border-gray-200">
              <input
                type="text"
                placeholder="Buscar por nombre o código"
                value={busquedaProducto}
                onChange={(e) => setBusquedaProducto(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && buscarProductos()}
                className="flex-1 px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 font-medium shadow-sm"
              />
              <button
                onClick={buscarProductos}
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide"
              >
                🔍 Buscar
              </button>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gradient-to-r from-blue-600 to-blue-700 text-white uppercase text-xs font-bold sticky top-0">
                  <tr>
                    <th className="px-4 py-3 text-left border-r border-blue-500">Código</th>
                    <th className="px-4 py-3 text-left border-r border-blue-500">Artículo</th>
                    <th className="px-4 py-3 text-right border-r border-blue-500">Precio</th>
                    <th className="px-4 py-3 text-right">Stock</th>
                  </tr>
                </thead>
                <tbody className="bg-white">
                  {cargandoProductos ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-gray-400 text-base">
                        <div className="flex flex-col items-center gap-2">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                          <span className="font-semibold">Buscando productos...</span>
                        </div>
                      </td>
                    </tr>
                  ) : productosEncontrados.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-gray-400 text-base">
                        <div className="flex flex-col items-center gap-2">
                          <svg className="w-12 h-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                          </svg>
                          <span className="font-semibold">Ingresa un criterio para buscar artículos.</span>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    productosEncontrados.map((producto, index) => (
                      <tr
                        key={producto.id}
                        onDoubleClick={() => agregarProductoPorLista(producto)}
                        className={`border-b border-gray-200 hover:bg-blue-50 cursor-pointer transition-colors ${index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}`}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-blue-600 font-semibold">
                          {producto.codigo}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-bold text-gray-800">{producto.nombre}</p>
                          <p className="text-xs text-gray-500 font-medium">{producto.categoria_nombre}</p>
                        </td>
                        <td className="px-4 py-3 text-right font-bold text-gray-800">{currency.format(Number(producto.precio_venta))}</td>
                        <td className="px-4 py-3 text-right font-bold text-gray-700">{producto.stock}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="bg-blue-50 border-t-2 border-blue-200 px-6 py-3 flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <span className="text-sm text-blue-800 font-semibold">Doble clic sobre un artículo para añadirlo a la factura.</span>
            </div>
          </div>
        </div>
      )}

      {mostrarAprobacion && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden border-2 border-gray-300">
            <div className="bg-gradient-to-r from-yellow-500 to-yellow-600 text-yellow-900 px-6 py-4 border-b-4 border-yellow-700">
              <h3 className="font-bold text-xl uppercase tracking-wide flex items-center gap-2">
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                Aprobación de Descuento
              </h3>
            </div>
            <div className="p-6 space-y-4">
              <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-lg">
                <p className="text-sm text-yellow-800 font-semibold">
                  El descuento de <span className="text-lg font-bold">{descuentoNumero}%</span> requiere aprobación del dueño o persona designada.
                </p>
              </div>
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-2 uppercase tracking-wide">Usuario Autorizado</label>
                <input
                  type="text"
                  value={aprobacionUsuario}
                  onChange={(e) => setAprobacionUsuario(e.target.value)}
                  placeholder="Ingrese usuario autorizado"
                  className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-400 focus:border-yellow-400 font-medium shadow-sm"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-2 uppercase tracking-wide">Contraseña</label>
                <input
                  type="password"
                  value={aprobacionPassword}
                  onChange={(e) => setAprobacionPassword(e.target.value)}
                  placeholder="Ingrese contraseña"
                  className="w-full px-4 py-2.5 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-400 focus:border-yellow-400 font-medium shadow-sm"
                />
              </div>
              {aprobacionError && (
                <div className="bg-red-100 border-l-4 border-red-500 p-3 rounded-r-lg">
                  <p className="text-sm text-red-700 font-semibold">{aprobacionError}</p>
                </div>
              )}
            </div>
            <div className="bg-gray-50 border-t-2 border-gray-200 px-6 py-4 flex justify-end gap-3">
              <button
                onClick={() => setMostrarAprobacion(false)}
                className="px-5 py-2.5 border-2 border-gray-400 text-gray-700 rounded-lg hover:bg-gray-100 font-bold shadow-sm hover:shadow-md transition-all uppercase tracking-wide"
              >
                Cancelar
              </button>
              <button
                onClick={confirmarAprobacion}
                className="px-5 py-2.5 bg-gradient-to-r from-green-500 to-green-600 text-white border-2 border-green-700 rounded-lg hover:from-green-600 hover:to-green-700 font-bold shadow-md hover:shadow-lg transition-all uppercase tracking-wide"
              >
                ✓ Autorizar Descuento
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
