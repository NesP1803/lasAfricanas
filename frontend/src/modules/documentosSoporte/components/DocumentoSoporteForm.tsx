import { useEffect, useMemo, useState } from 'react';
import {
  type CategoriaOption,
  documentosSoporteApi,
  type CrearDocumentoSoportePayload,
  type ImpuestoOption,
  type ProveedorSugerencia,
} from '../services/documentosSoporteApi';

interface DocumentoSoporteFormProps {
  loading: boolean;
  onSubmit: (payload: CrearDocumentoSoportePayload) => Promise<void>;
}

export default function DocumentoSoporteForm({ onSubmit, loading }: DocumentoSoporteFormProps) {
  const [proveedorNombre, setProveedorNombre] = useState('');
  const [proveedorDocumento, setProveedorDocumento] = useState('');
  const [tipoDocumentoProveedor, setTipoDocumentoProveedor] = useState('CC');
  const [proveedorId, setProveedorId] = useState<number | undefined>(undefined);
  const [proveedoresSugeridos, setProveedoresSugeridos] = useState<ProveedorSugerencia[]>([]);
  const [mostrarSugerencias, setMostrarSugerencias] = useState(false);
  const [buscandoProveedor, setBuscandoProveedor] = useState(false);
  const [direccionProveedor, setDireccionProveedor] = useState('');
  const [emailProveedor, setEmailProveedor] = useState('');
  const [telefonoProveedor, setTelefonoProveedor] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [codigoReferencia, setCodigoReferencia] = useState('');
  const [categoriaId, setCategoriaId] = useState('');
  const [categorias, setCategorias] = useState<CategoriaOption[]>([]);
  const [unidadMedida, setUnidadMedida] = useState('N/A');
  const [impuestos, setImpuestos] = useState<ImpuestoOption[]>([]);
  const [ivaMercancia, setIvaMercancia] = useState('0');
  const [cantidad, setCantidad] = useState('1');
  const [valorUnitario, setValorUnitario] = useState('');
  const [observacion, setObservacion] = useState('');

  const proveedorExacto = useMemo(
    () => proveedoresSugeridos.find((item) => item.nombre.trim().toLowerCase() === proveedorNombre.trim().toLowerCase()),
    [proveedoresSugeridos, proveedorNombre],
  );

  const inferTipoDocumento = (nit?: string) => (nit && nit.trim() ? 'NIT' : 'CC');

  const handleProveedorSelect = (proveedor: ProveedorSugerencia) => {
    setProveedorId(proveedor.id);
    setProveedorNombre(proveedor.nombre);
    setProveedorDocumento((proveedor.nit ?? '').trim());
    setTipoDocumentoProveedor(inferTipoDocumento(proveedor.nit));
    setDireccionProveedor((proveedor.direccion ?? '').trim());
    setEmailProveedor((proveedor.email ?? '').trim());
    setTelefonoProveedor((proveedor.telefono ?? '').trim());
    setMostrarSugerencias(false);
  };

  const handleProveedorNombreChange = async (value: string) => {
    setProveedorNombre(value);
    setProveedorId(undefined);
    setMostrarSugerencias(true);
    if (!value.trim()) {
      setProveedoresSugeridos([]);
      return;
    }
    setBuscandoProveedor(true);
    try {
      const resultados = await documentosSoporteApi.buscarProveedores(value.trim());
      setProveedoresSugeridos(resultados);
    } finally {
      setBuscandoProveedor(false);
    }
  };

  const completarSiCoincideExacto = () => {
    if (proveedorExacto) {
      handleProveedorSelect(proveedorExacto);
    }
  };

  useEffect(() => {
    const loadCatalogosArticulo = async () => {
      try {
        const [categoriasData, impuestosData] = await Promise.all([
          documentosSoporteApi.getCategorias(),
          documentosSoporteApi.getImpuestos(),
        ]);
        setCategorias(categoriasData);
        setImpuestos(impuestosData);
      } catch {
        setCategorias([]);
        setImpuestos([]);
      }
    };
    loadCatalogosArticulo();
  }, []);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (proveedorExacto && !proveedorId) {
      handleProveedorSelect(proveedorExacto);
    }
    await onSubmit({
      proveedor_nombre: proveedorNombre.trim(),
      proveedor_documento: proveedorDocumento.trim(),
      proveedor_tipo_documento: tipoDocumentoProveedor,
      proveedor_id: proveedorId,
      provider_address: direccionProveedor.trim(),
      provider_email: emailProveedor.trim(),
      provider_phone: telefonoProveedor.trim(),
      provider_country_code: 'CO',
      observation: observacion.trim(),
      items: [
        {
          codigo_referencia: codigoReferencia.trim(),
          categoria_id: categoriaId ? Number(categoriaId) : undefined,
          descripcion: descripcion.trim(),
          cantidad: Number(cantidad),
          precio: Number(valorUnitario),
          unidad_medida: unidadMedida.trim(),
          iva_porcentaje: ivaMercancia.trim(),
        },
      ],
    });
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg bg-white p-6 shadow">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="relative flex flex-col gap-1 text-sm text-slate-700">
          Proveedor nombre
          <input
            value={proveedorNombre}
            onChange={(event) => void handleProveedorNombreChange(event.target.value)}
            onFocus={() => setMostrarSugerencias(true)}
            onBlur={() => {
              window.setTimeout(() => {
                completarSiCoincideExacto();
                setMostrarSugerencias(false);
              }, 150);
            }}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
            placeholder="Escribe para autocompletar proveedor..."
          />
          {mostrarSugerencias && (
            <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-20 max-h-56 overflow-y-auto rounded-md border border-slate-200 bg-white shadow">
              {buscandoProveedor ? (
                <div className="px-3 py-2 text-xs text-slate-500">Buscando proveedores...</div>
              ) : proveedoresSugeridos.length === 0 ? (
                <div className="px-3 py-2 text-xs text-slate-500">Sin coincidencias.</div>
              ) : (
                proveedoresSugeridos.map((prov) => (
                  <button
                    key={prov.id}
                    type="button"
                    onMouseDown={() => handleProveedorSelect(prov)}
                    className="block w-full px-3 py-2 text-left text-xs hover:bg-slate-50"
                  >
                    <div className="font-semibold text-slate-700">{prov.nombre}</div>
                    <div className="text-slate-500">{prov.nit || 'Sin NIT'}</div>
                  </button>
                ))
              )}
            </div>
          )}
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Proveedor documento
          <input
            value={proveedorDocumento}
            onChange={(event) => setProveedorDocumento(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Dirección proveedor
          <input
            value={direccionProveedor}
            onChange={(event) => setDireccionProveedor(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Email proveedor
          <input
            type="email"
            value={emailProveedor}
            onChange={(event) => setEmailProveedor(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Teléfono proveedor
          <input
            value={telefonoProveedor}
            onChange={(event) => setTelefonoProveedor(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Tipo documento proveedor
          <select
            value={tipoDocumentoProveedor}
            onChange={(event) => setTipoDocumentoProveedor(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          >
            <option value="CC">CC</option>
            <option value="CE">CE</option>
            <option value="NIT">NIT</option>
            <option value="PASAPORTE">Pasaporte</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Código referencia
          <input
            value={codigoReferencia}
            onChange={(event) => setCodigoReferencia(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Categoría
          <select
            value={categoriaId}
            onChange={(event) => setCategoriaId(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          >
            <option value="">Seleccione una categoría</option>
            {categorias.map((categoria) => (
              <option key={categoria.id} value={categoria.id}>
                {categoria.nombre}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          U/M
          <select
            value={unidadMedida}
            onChange={(event) => setUnidadMedida(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          >
            <option value="N/A">N/A</option>
            <option value="KG">KG</option>
            <option value="LT">LT</option>
            <option value="MT">MT</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          IVA (%)
          <select
            value={ivaMercancia}
            onChange={(event) => setIvaMercancia(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          >
            <option value="0">Exento (0%)</option>
            {impuestos.map((impuesto) => (
              <option key={impuesto.id} value={impuesto.porcentaje}>
                {impuesto.nombre}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Descripción
          <textarea
            value={descripcion}
            onChange={(event) => setDescripcion(event.target.value)}
            className="min-h-24 rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-700 md:col-span-2">
          Observación
          <input
            value={observacion}
            onChange={(event) => setObservacion(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            maxLength={250}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Cantidad
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={cantidad}
            onChange={(event) => setCantidad(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-slate-700">
          Valor unitario
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorUnitario}
            onChange={(event) => setValorUnitario(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 outline-none ring-blue-200 focus:ring"
            required
          />
        </label>
      </div>

      <div className="mt-5 flex justify-end">
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-70"
          disabled={loading}
        >
          {loading ? 'Emitiendo...' : 'Emitir documento soporte'}
        </button>
      </div>
    </form>
  );
}
