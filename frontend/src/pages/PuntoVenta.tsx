import { useState } from 'react';
import { Search, Trash2, Plus, Minus } from 'lucide-react';
import { inventarioApi } from '../api/inventario';
import { ventasApi } from '../api/ventas';
import { useAuth } from '../contexts/AuthContext';
import type {  Producto } from "../api/inventario";
import type {Cliente, DetalleVenta } from "../api/ventas";

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
    <div className="h-full flex flex-col bg-yellow-50">
      {/* Header */}
      <div className="bg-blue-600 text-white p-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <label className="text-xs font-semibold block mb-1">DIGITE Nº/CC DEL CLIENTE</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Número de documento"
                value={buscarCliente}
                onChange={(e) => setBuscarCliente(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && buscarClientePorDocumento()}
                className="px-3 py-2 rounded text-gray-900 w-48"
              />
              <button
                onClick={buscarClientePorDocumento}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded font-bold"
              >
                ✓
              </button>
            </div>
          </div>

          {cliente && (
            <div className="bg-white text-gray-900 px-4 py-2 rounded">
              <p className="font-bold text-lg">{cliente.nombre}</p>
              <p className="text-sm">{cliente.numero_documento}</p>
            </div>
          )}
        </div>

        <div className="text-right">
          <p className="text-xs">VENDEDOR</p>
          <p className="font-bold text-lg">{user?.username.toUpperCase()}</p>
        </div>
      </div>

      {/* Tabla de productos */}
      <div className="flex-1 bg-white m-3 rounded-lg shadow-lg overflow-hidden flex flex-col">
        <div className="bg-gray-100 px-4 py-2 border-b grid grid-cols-12 gap-2 font-bold text-sm">
          <div className="col-span-1">Cant</div>
          <div className="col-span-2">Código</div>
          <div className="col-span-4">Artículo</div>
          <div className="col-span-1 text-center">I.V.A.</div>
          <div className="col-span-1 text-right">Total</div>
          <div className="col-span-1 text-right">PRECIO U</div>
          <div className="col-span-1 text-center">Desc %</div>
          <div className="col-span-1 text-center">Acciones</div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {carrito.map((item, index) => (
            <div
              key={item.producto.id}
              className={`px-4 py-2 grid grid-cols-12 gap-2 items-center border-b hover:bg-yellow-50 ${
                index % 2 === 0 ? 'bg-white' : 'bg-gray-50'
              }`}
            >
              <div className="col-span-1 flex items-center gap-1">
                <button
                  onClick={() => actualizarCantidad(item.producto.id, item.cantidad - 1)}
                  className="p-1 bg-gray-200 hover:bg-gray-300 rounded"
                >
                  <Minus size={14} />
                </button>
                <span className="font-bold w-8 text-center">{item.cantidad}</span>
                <button
                  onClick={() => actualizarCantidad(item.producto.id, item.cantidad + 1)}
                  className="p-1 bg-gray-200 hover:bg-gray-300 rounded"
                >
                  <Plus size={14} />
                </button>
              </div>
              <div className="col-span-2 font-mono text-sm">{item.producto.codigo}</div>
              <div className="col-span-4 font-semibold">{item.producto.nombre}</div>
              <div className="col-span-1 text-center">{item.producto.iva_porcentaje}%</div>
              <div className="col-span-1 text-right font-bold">
                ${item.subtotal.toLocaleString('es-CO', { minimumFractionDigits: 0 })}
              </div>
              <div className="col-span-1 text-right">
                ${item.precio_unitario.toLocaleString('es-CO', { minimumFractionDigits: 0 })}
              </div>
              <div className="col-span-1 text-center">{item.descuento_unitario}</div>
              <div className="col-span-1 text-center">
                <button
                  onClick={() => eliminarDelCarrito(item.producto.id)}
                  className="p-2 bg-red-500 hover:bg-red-600 text-white rounded"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer con totales y controles */}
      <div className="bg-gray-100 border-t-4 border-blue-600 p-4">
        <div className="grid grid-cols-3 gap-4">
          {/* Búsqueda de código */}
          <div>
            <label className="block text-sm font-bold mb-2">DIGITE CÓDIGO DE ARTÍCULO</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={codigoBusqueda}
                onChange={(e) => setCodigoBusqueda(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && buscarProducto()}
                placeholder="Código..."
                className="flex-1 px-4 py-3 border-2 border-gray-300 rounded-lg text-lg font-mono"
                autoFocus
              />
              <button
                onClick={buscarProducto}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
              >
                <Search size={24} />
              </button>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-bold mb-2">DESCUENTO GENERAL</label>
              <input
                type="number"
                min="0"
                max="100"
                value={descuentoGeneral}
                onChange={(e) => setDescuentoGeneral(parseFloat(e.target.value) || 0)}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg text-center text-2xl font-bold text-blue-600"
              />
            </div>
          </div>

          {/* Botones de acción */}
          <div className="flex flex-col justify-center gap-3">
            <button
              onClick={() => procesarVenta('COTIZACION')}
              disabled={procesando || carrito.length === 0 || !cliente}
              className="py-4 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg font-bold text-lg disabled:bg-gray-400"
            >
              📄 COTIZAR
            </button>
            <button
              onClick={() => procesarVenta('REMISION')}
              disabled={procesando || carrito.length === 0 || !cliente}
              className="py-4 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-bold text-lg disabled:bg-gray-400"
            >
              📋 REMISIÓN
            </button>
            <button
              onClick={() => procesarVenta('FACTURA')}
              disabled={procesando || carrito.length === 0 || !cliente}
              className="py-4 bg-green-600 hover:bg-green-700 text-white rounded-lg font-bold text-lg disabled:bg-gray-400"
            >
              💵 FACTURAR
            </button>
          </div>

          {/* Totales */}
          <div className="space-y-2">
            <div className="bg-white p-3 rounded-lg flex justify-between items-center">
              <span className="font-bold text-lg">SUBTOTAL:</span>
              <span className="text-2xl font-bold">
                ${subtotal.toLocaleString('es-CO', { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="bg-white p-3 rounded-lg flex justify-between items-center">
              <span className="font-bold text-lg">IMPUESTOS:</span>
              <span className="text-2xl font-bold">
                ${iva.toLocaleString('es-CO', { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="bg-white p-3 rounded-lg flex justify-between items-center">
              <span className="font-bold text-lg text-red-600">DESCUENTOS:</span>
              <span className="text-2xl font-bold text-red-600">
                -${descuentoValor.toLocaleString('es-CO', { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="bg-orange-400 p-4 rounded-lg flex justify-between items-center">
              <span className="font-bold text-xl text-white">TOTAL A PAGAR:</span>
              <span className="text-4xl font-bold text-white">
                ${totalPagar.toLocaleString('es-CO', { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-bold mb-1">MEDIO DE PAGO</label>
                <select
                  value={medioPago}
                  onChange={(e: any) => setMedioPago(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-gray-300 rounded-lg font-bold"
                >
                  <option value="EFECTIVO">EFECTIVO</option>
                  <option value="TARJETA">TARJETA</option>
                  <option value="TRANSFERENCIA">TRANSFERENCIA</option>
                  <option value="CREDITO">CRÉDITO</option>
                </select>
              </div>

              {medioPago === 'EFECTIVO' && (
                <div>
                  <label className="block text-xs font-bold mb-1">EFECTIVO RECIBIDO</label>
                  <input
                    type="number"
                    value={efectivoRecibido}
                    onChange={(e) => setEfectivoRecibido(e.target.value)}
                    className="w-full px-3 py-2 border-2 border-gray-300 rounded-lg text-right font-bold text-lg bg-black text-green-400"
                  />
                </div>
              )}
            </div>

            {medioPago === 'EFECTIVO' && efectivo > 0 && (
              <div className="bg-blue-600 p-3 rounded-lg flex justify-between items-center">
                <span className="font-bold text-lg text-white">CAMBIO:</span>
                <span className="text-3xl font-bold text-white">
                  ${Math.max(0, cambio).toLocaleString('es-CO', { minimumFractionDigits: 2 })}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}