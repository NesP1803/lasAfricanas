import { useState } from 'react';
import { Search, Trash2, Plus, Minus } from 'lucide-react';
import { inventarioApi } from '../api/inventario';
import { ventasApi, } from '../api/ventas';
import { useAuth } from '../contexts/AuthContext';
import type {  Producto } from "../api/inventario";
import type {  Cliente, DetalleVenta } from "../api/ventas";

interface ItemCarrito {
  producto: Producto;
  cantidad: number;
  precio_unitario: number;
  descuento_unitario: number;
  subtotal: number;
}

export default function PuntoVenta() {
  const { user } = useAuth();
  const [codigoBusqueda, setCodigoBusqueda] = useState('');
  const [carrito, setCarrito] = useState<ItemCarrito[]>([]);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [buscarCliente, setBuscarCliente] = useState('');
  const [descuentoGeneral, setDescuentoGeneral] = useState(0);
  const [medioPago, setMedioPago] = useState<'EFECTIVO' | 'TARJETA' | 'TRANSFERENCIA' | 'CREDITO'>('EFECTIVO');
  const [efectivoRecibido, setEfectivoRecibido] = useState('');
  const [procesando, setProcesando] = useState(false);

  // Buscar producto por código
  const buscarProducto = async () => {
    if (!codigoBusqueda.trim()) return;

    try {
      const producto = await inventarioApi.buscarPorCodigo(codigoBusqueda.trim());
      agregarAlCarrito(producto);
      setCodigoBusqueda('');
    } catch (error) {
      alert('Producto no encontrado');
      setCodigoBusqueda('');
    }
  };

  // Agregar producto al carrito
  const agregarAlCarrito = (producto: Producto) => {
    const existente = carrito.find((item) => item.producto.id === producto.id);

    if (existente) {
      actualizarCantidad(producto.id, existente.cantidad + 1);
    } else {
      const nuevo: ItemCarrito = {
        producto,
        cantidad: 1,
        precio_unitario: parseFloat(producto.precio_venta),
        descuento_unitario: 0,
        subtotal: parseFloat(producto.precio_venta),
      };
      setCarrito([...carrito, nuevo]);
    }
  };

  // Actualizar cantidad
  const actualizarCantidad = (productoId: number, nuevaCantidad: number) => {
    if (nuevaCantidad <= 0) {
      eliminarDelCarrito(productoId);
      return;
    }

    setCarrito(
      carrito.map((item) =>
        item.producto.id === productoId
          ? {
              ...item,
              cantidad: nuevaCantidad,
              subtotal: (item.precio_unitario - item.descuento_unitario) * nuevaCantidad,
            }
          : item
      )
    );
  };

  // Eliminar del carrito
  const eliminarDelCarrito = (productoId: number) => {
    setCarrito(carrito.filter((item) => item.producto.id !== productoId));
  };

  // Buscar cliente
  const buscarClientePorDocumento = async () => {
    if (!buscarCliente.trim()) return;

    try {
      const clienteEncontrado = await ventasApi.buscarCliente(buscarCliente.trim());
      setCliente(clienteEncontrado);
    } catch (error) {
      alert('Cliente no encontrado');
    }
  };

  // Calcular totales
  const subtotal = carrito.reduce((sum, item) => sum + item.subtotal, 0);
  const descuentoValor = (subtotal * descuentoGeneral) / 100;
  const baseImponible = subtotal - descuentoValor;
  const iva = carrito.reduce(
    (sum, item) =>
      sum + (item.subtotal - (item.subtotal * descuentoGeneral) / 100) * (parseFloat(item.producto.iva_porcentaje) / 100),
    0
  );
  const totalPagar = baseImponible + iva;
  const efectivo = parseFloat(efectivoRecibido) || 0;
  const cambio = efectivo - totalPagar;

  // Procesar venta
  const procesarVenta = async (tipoComprobante: 'COTIZACION' | 'REMISION' | 'FACTURA') => {
    if (!cliente) {
      alert('Debe seleccionar un cliente');
      return;
    }

    if (carrito.length === 0) {
      alert('El carrito está vacío');
      return;
    }

    if (medioPago === 'EFECTIVO' && efectivo < totalPagar) {
      alert('El efectivo recibido es insuficiente');
      return;
    }

    setProcesando(true);

    try {
      const detalles: DetalleVenta[] = carrito.map((item) => ({
        producto: item.producto.id,
        cantidad: item.cantidad,
        precio_unitario: item.precio_unitario.toString(),
        descuento_unitario: item.descuento_unitario.toString(),
        iva_porcentaje: item.producto.iva_porcentaje,
        subtotal: item.subtotal.toString(),
        total: item.subtotal.toString(),
      }));

      const ventaData = {
        tipo_comprobante: tipoComprobante,
        cliente: cliente.id,
        vendedor: user!.id,
        subtotal: subtotal.toFixed(2),
        descuento_porcentaje: descuentoGeneral.toString(),
        descuento_valor: descuentoValor.toFixed(2),
        iva: iva.toFixed(2),
        total: totalPagar.toFixed(2),
        medio_pago: medioPago,
        efectivo_recibido: efectivo.toString(),
        cambio: Math.max(0, cambio).toFixed(2),
        detalles,
      };

      const venta = await ventasApi.crearVenta(ventaData);

      alert(`${venta.tipo_comprobante_display} #${venta.numero_comprobante} creada exitosamente`);

      // Limpiar
      setCarrito([]);
      setDescuentoGeneral(0);
      setEfectivoRecibido('');
    } catch (error: any) {
      console.error('Error:', error);

      if (error.requiere_aprobacion) {
        alert(`El descuento de ${descuentoGeneral}% requiere autorización del gerente.`);
      } else if (error.error) {
        alert(error.error);
      } else {
        alert('Error al procesar la venta');
      }
    } finally {
      setProcesando(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-gradient-to-b from-gray-200 to-gray-300 border-b-2 border-gray-400 p-2">
        {/* Título y Fecha */}
        <div className="flex justify-between items-center mb-2 pb-2 border-b border-gray-400">
          <h1 className="text-sm font-bold text-gray-800">
            VENTANA DE FACTURACIÓN: GENERAR NUEVA FACTURA O REMISIÓN
          </h1>
          <span className="text-xs text-gray-700">
            {new Date().toLocaleString('es-CO', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit'
            })}
          </span>
        </div>

        {/* Campos superiores */}
        <div className="grid grid-cols-12 gap-2 items-end text-xs">
          {/* DIGITE NIT/CC DEL CLIENTE */}
          <div className="col-span-2">
            <label className="font-bold text-gray-800 block mb-1">DIGITE NIT/CC DEL CLIENTE</label>
            <input
              type="text"
              placeholder="Documento"
              value={buscarCliente}
              onChange={(e) => setBuscarCliente(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && buscarClientePorDocumento()}
              className="w-full px-2 py-1 border border-gray-400 rounded text-gray-900 text-sm"
            />
          </div>

          {/* CLIENTE Y/O RAZON SOCIAL */}
          <div className="col-span-3">
            <label className="font-bold text-gray-800 block mb-1">CLIENTE Y/O RAZON SOCIAL</label>
            <input
              type="text"
              value={cliente?.nombre || 'CLIENTE GENERAL'}
              readOnly
              className="w-full px-2 py-1 border border-gray-400 rounded bg-white text-gray-900 text-sm font-semibold"
            />
          </div>

          {/* VENDEDOR */}
          <div className="col-span-2">
            <label className="font-bold text-gray-800 block mb-1">VENDEDOR</label>
            <input
              type="text"
              value={user?.username.toUpperCase() || ''}
              readOnly
              className="w-full px-2 py-1 border border-gray-400 rounded bg-blue-100 text-gray-900 text-sm font-semibold"
            />
          </div>

          {/* GENERAR FACTURA# */}
          <div className="col-span-1">
            <label className="font-bold text-gray-800 block mb-1">GENERAR FACTURA#</label>
            <select className="w-full px-2 py-1 border border-gray-400 rounded bg-yellow-100 text-gray-900 text-sm">
              <option>FAC</option>
            </select>
          </div>

          {/* Número */}
          <div className="col-span-1">
            <label className="font-bold text-gray-800 block mb-1">&nbsp;</label>
            <input
              type="text"
              value="100091"
              readOnly
              className="w-full px-2 py-1 border border-gray-400 rounded bg-white text-gray-900 text-sm text-center"
            />
          </div>

          {/* GENERAR REMISION# */}
          <div className="col-span-1">
            <label className="font-bold text-gray-800 block mb-1">GENERAR REMISION#</label>
            <input
              type="text"
              value="154239"
              readOnly
              className="w-full px-2 py-1 border border-gray-400 rounded bg-white text-gray-900 text-sm text-center"
            />
          </div>

          {/* MEDIO DE PAGO */}
          <div className="col-span-1">
            <label className="font-bold text-gray-800 block mb-1">MEDIO DE PAGO</label>
            <select
              value={medioPago}
              onChange={(e: any) => setMedioPago(e.target.value)}
              className="w-full px-2 py-1 border border-gray-400 rounded bg-white text-gray-900 text-sm"
            >
              <option value="EFECTIVO">EFECTIVO</option>
              <option value="TARJETA">TARJETA</option>
              <option value="TRANSFERENCIA">TRANSFER</option>
              <option value="CREDITO">CREDITO</option>
            </select>
          </div>

          {/* AUT VOUCHER */}
          <div className="col-span-1">
            <label className="font-bold text-gray-800 block mb-1">AUT VOUCHER</label>
            <input
              type="text"
              defaultValue="0"
              className="w-full px-2 py-1 border border-gray-400 rounded bg-white text-gray-900 text-sm text-center"
            />
          </div>
        </div>
      </div>

      {/* Tabla de productos */}
      <div className="flex-1 bg-white m-2 border-2 border-gray-400 overflow-hidden flex flex-col">
        <div className="bg-yellow-400 px-2 py-1 border-b-2 border-gray-400 grid grid-cols-12 gap-1 font-bold text-xs">
          <div className="col-span-1 text-center">Cant</div>
          <div className="col-span-2">Código</div>
          <div className="col-span-3">Artículo</div>
          <div className="col-span-1 text-center">I.V.A.</div>
          <div className="col-span-1 text-right">Total</div>
          <div className="col-span-1 text-right">PRECIO U</div>
          <div className="col-span-1 text-center">Desc %</div>
          <div className="col-span-1 text-right">ValorDes</div>
          <div className="col-span-1 text-center">stock</div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {carrito.map((item, index) => (
            <div
              key={item.producto.id}
              className={`px-2 py-1 grid grid-cols-12 gap-1 items-center border-b border-gray-300 text-xs ${
                index % 2 === 0 ? 'bg-white' : 'bg-blue-50'
              }`}
            >
              <div className="col-span-1 flex items-center justify-center gap-0.5">
                <button
                  onClick={() => actualizarCantidad(item.producto.id, item.cantidad - 1)}
                  className="p-0.5 bg-gray-300 hover:bg-gray-400 rounded text-xs"
                >
                  <Minus size={12} />
                </button>
                <span className="font-bold w-8 text-center bg-white border border-gray-300 px-1">
                  {item.cantidad}
                </span>
                <button
                  onClick={() => actualizarCantidad(item.producto.id, item.cantidad + 1)}
                  className="p-0.5 bg-gray-300 hover:bg-gray-400 rounded text-xs"
                >
                  <Plus size={12} />
                </button>
              </div>
              <div className="col-span-2 font-mono text-xs">{item.producto.codigo}</div>
              <div className="col-span-3 font-semibold text-xs uppercase">{item.producto.nombre}</div>
              <div className="col-span-1 text-center">{item.producto.iva_porcentaje}</div>
              <div className="col-span-1 text-right font-bold">
                {item.subtotal.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </div>
              <div className="col-span-1 text-right">
                {item.precio_unitario.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </div>
              <div className="col-span-1 text-center font-bold">{item.descuento_unitario}</div>
              <div className="col-span-1 text-right">{item.descuento_unitario}</div>
              <div className="col-span-1 text-center font-bold">{item.producto.stock || 0}</div>
            </div>
          ))}
          {carrito.length === 0 && (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
              No hay productos en el carrito
            </div>
          )}
        </div>
      </div>

      {/* Footer con totales y controles */}
      <div className="bg-gradient-to-b from-gray-200 to-gray-300 border-t-2 border-gray-400 p-2">
        <div className="grid grid-cols-2 gap-3">
          {/* Columna izquierda: Controles */}
          <div className="space-y-2">
            {/* DIGITE CODIGO DE ARTICULO */}
            <div className="border-2 border-gray-400 bg-white p-2 rounded">
              <label className="block text-xs font-bold mb-1 text-gray-800">
                DIGITE CODIGO DE ARTICULO 🔍
              </label>
              <div className="flex gap-1 mb-2">
                <input
                  type="text"
                  value={codigoBusqueda}
                  onChange={(e) => setCodigoBusqueda(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && buscarProducto()}
                  placeholder="Código..."
                  className="flex-1 px-2 py-1 border-2 border-gray-400 rounded text-sm font-mono"
                  autoFocus
                />
              </div>
              <div className="flex gap-1">
                <button
                  onClick={buscarProducto}
                  className="flex-1 px-2 py-1.5 bg-gray-300 hover:bg-gray-400 border border-gray-500 rounded text-xs font-bold"
                  title="Buscar"
                >
                  🔍
                </button>
                <button
                  className="flex-1 px-2 py-1.5 bg-gray-300 hover:bg-gray-400 border border-gray-500 rounded text-xs font-bold"
                  title="Editar"
                >
                  ✏️
                </button>
                <button
                  className="flex-1 px-2 py-1.5 bg-gray-300 hover:bg-gray-400 border border-gray-500 rounded text-xs font-bold"
                  title="Agregar"
                >
                  ➕
                </button>
                <button
                  className="flex-1 px-2 py-1.5 bg-gray-300 hover:bg-gray-400 border border-gray-500 rounded text-xs font-bold"
                  title="Información"
                >
                  ℹ️
                </button>
              </div>
            </div>

            {/* DESCUENTO GENERAL */}
            <div className="border-2 border-gray-400 bg-white p-2 rounded">
              <label className="block text-xs font-bold mb-1 text-gray-800">
                DESCUENTO GENERAL ❓
              </label>
              <div className="flex gap-2 items-center mb-2">
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={descuentoGeneral}
                  onChange={(e) => setDescuentoGeneral(parseFloat(e.target.value) || 0)}
                  className="w-20 px-2 py-1 border-2 border-blue-400 rounded text-center text-lg font-bold text-blue-600"
                />
                <span className="text-sm font-bold">%</span>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => procesarVenta('COTIZACION')}
                  disabled={procesando || carrito.length === 0 || !cliente}
                  className="flex-1 px-2 py-2 bg-blue-500 hover:bg-blue-600 text-white border border-blue-700 rounded text-xs font-bold disabled:bg-gray-400 disabled:border-gray-500"
                  title="Cotizar"
                >
                  ⭕ COTIZAR
                </button>
                <button
                  onClick={() => procesarVenta('REMISION')}
                  disabled={procesando || carrito.length === 0 || !cliente}
                  className="flex-1 px-2 py-2 bg-green-600 hover:bg-green-700 text-white border border-green-800 rounded text-xs font-bold disabled:bg-gray-400 disabled:border-gray-500"
                  title="Remisión"
                >
                  📋 REMISION
                </button>
                <button
                  onClick={() => procesarVenta('FACTURA')}
                  disabled={procesando || carrito.length === 0 || !cliente}
                  className="flex-1 px-2 py-2 bg-red-600 hover:bg-red-700 text-white border border-red-800 rounded text-xs font-bold disabled:bg-gray-400 disabled:border-gray-500"
                  title="Facturar"
                >
                  💵 $FACTURAR
                </button>
              </div>
            </div>
          </div>

          {/* Columna derecha: Totales */}
          <div className="space-y-1">
            {/* SUBTOTAL */}
            <div className="bg-white border-2 border-gray-400 p-1 rounded flex justify-between items-center">
              <span className="font-bold text-sm text-gray-800">SUBTOTAL :</span>
              <span className="text-xl font-bold text-gray-900">
                {subtotal.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* IMPUESTOS */}
            <div className="bg-white border-2 border-gray-400 p-1 rounded flex justify-between items-center">
              <span className="font-bold text-sm text-gray-800">IMPUESTOS :</span>
              <span className="text-xl font-bold text-gray-900">
                {iva.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* DESCUENTOS */}
            <div className="bg-white border-2 border-gray-400 p-1 rounded flex justify-between items-center">
              <span className="font-bold text-sm text-gray-800">DESCUENTOS :</span>
              <span className="text-xl font-bold text-red-600">
                {descuentoValor > 0 ? '-' : ''}
                {descuentoValor.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* TOTAL A PAGAR */}
            <div className="bg-gradient-to-r from-orange-400 to-orange-500 border-2 border-orange-600 p-2 rounded flex justify-between items-center">
              <span className="font-bold text-base text-white">TOTAL A PAGAR :</span>
              <span className="text-3xl font-bold text-white">
                {totalPagar.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* EFECTIVO RECIBIDO */}
            <div className="bg-black border-2 border-gray-600 p-2 rounded flex justify-between items-center">
              <span className="font-bold text-sm text-green-400">EFECTIVO RECIBIDO :</span>
              <span className="text-2xl font-bold text-green-400">
                {efectivo.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* CAMBIO */}
            <div className="bg-blue-600 border-2 border-blue-800 p-1 rounded flex justify-between items-center">
              <span className="font-bold text-sm text-white">CAMBIO :</span>
              <span className="text-2xl font-bold text-white">
                {Math.max(0, cambio).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* DIGITE EFECTIVO RECIBIDO */}
            <div className="border-2 border-gray-400 bg-white p-1 rounded">
              <label className="block text-xs font-bold mb-1 text-gray-800">
                DIGITE EFECTIVO RECIBIDO ⭕
              </label>
              <input
                type="number"
                value={efectivoRecibido}
                onChange={(e) => setEfectivoRecibido(e.target.value)}
                className="w-full px-2 py-1 border-2 border-gray-400 rounded text-right font-bold text-xl bg-gray-100"
                placeholder="50000"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}