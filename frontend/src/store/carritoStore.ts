import { create } from 'zustand';

interface ItemCarrito {
  producto_id: number;
  codigo: string;
  nombre: string;
  cantidad: number;
  precio_unitario: number;
  descuento: number;
  iva_porcentaje: number;
  subtotal: number;
  total: number;
  stock: number;
}

interface CarritoState {
  items: ItemCarrito[];
  descuentoGlobal: number;
  
  // Actions
  agregarItem: (item: Omit<ItemCarrito, 'subtotal' | 'total'>) => void;
  eliminarItem: (producto_id: number) => void;
  actualizarCantidad: (producto_id: number, cantidad: number) => void;
  setDescuentoGlobal: (descuento: number) => void;
  limpiarCarrito: () => void;
  calcularTotales: () => { subtotal: number; descuento: number; iva: number; total: number };
}

const calcularItemTotal = (item: Omit<ItemCarrito, 'subtotal' | 'total'>) => {
  const subtotal = item.cantidad * item.precio_unitario - item.descuento;
  const iva = subtotal * (item.iva_porcentaje / 100);
  const total = subtotal + iva;
  return { subtotal, total };
};

export const useCarritoStore = create<CarritoState>((set, get) => ({
  items: [],
  descuentoGlobal: 0,

  agregarItem: (item) => {
    const { subtotal, total } = calcularItemTotal(item);
    const nuevoItem = { ...item, subtotal, total };

    set((state) => {
      const itemExistente = state.items.find(
        (i) => i.producto_id === item.producto_id
      );

      if (itemExistente) {
        return {
          items: state.items.map((i) =>
            i.producto_id === item.producto_id
              ? {
                  ...i,
                  cantidad: i.cantidad + item.cantidad,
                  ...calcularItemTotal({
                    ...i,
                    cantidad: i.cantidad + item.cantidad,
                  }),
                }
              : i
          ),
        };
      }

      return { items: [...state.items, nuevoItem] };
    });
  },

  eliminarItem: (producto_id) =>
    set((state) => ({
      items: state.items.filter((item) => item.producto_id !== producto_id),
    })),

  actualizarCantidad: (producto_id, cantidad) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.producto_id === producto_id
          ? {
              ...item,
              cantidad,
              ...calcularItemTotal({ ...item, cantidad }),
            }
          : item
      ),
    })),

  setDescuentoGlobal: (descuento) => set({ descuentoGlobal: descuento }),

  limpiarCarrito: () => set({ items: [], descuentoGlobal: 0 }),

  calcularTotales: () => {
    const state = get();
    const subtotal = state.items.reduce((sum, item) => sum + item.subtotal, 0);
    const descuento = subtotal * (state.descuentoGlobal / 100);
    const iva = state.items.reduce(
      (sum, item) => sum + item.subtotal * (item.iva_porcentaje / 100),
      0
    );
    const total = subtotal - descuento + iva;

    return { subtotal, descuento, iva, total };
  },
}));