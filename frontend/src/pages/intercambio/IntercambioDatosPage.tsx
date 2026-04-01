import { useEffect, useMemo, useState } from 'react';
import { intercambioApi } from '../../api/intercambio';

export default function IntercambioDatosPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<any>(null);
  const [imports, setImports] = useState<any[]>([]);
  const [plantillas, setPlantillas] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [exportJob, setExportJob] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const cargarBase = async () => {
    const [imp, pla, prof] = await Promise.all([
      intercambioApi.listarImportaciones(),
      intercambioApi.listarPlantillas(),
      intercambioApi.perfilesExportacion(),
    ]);
    setImports(imp.results || imp);
    setPlantillas(pla);
    setProfiles(prof);
  };

  useEffect(() => {
    void cargarBase();
  }, []);

  const doAnalyze = async () => {
    setLoading(true);
    try {
      const result = await intercambioApi.analizar(files);
      setJob(result);
      await cargarBase();
    } finally {
      setLoading(false);
    }
  };

  const doExecute = async () => {
    if (!job?.id) return;
    const result = await intercambioApi.ejecutar(job.id);
    alert(`Importación ejecutada: ${JSON.stringify(result.summary)}`);
    await cargarBase();
  };

  const totalWarnings = useMemo(
    () => (job?.files || []).reduce((acc: number, f: any) => acc + (f.sheets || []).filter((s: any) => s.entidad_detectada === 'ambigua').length, 0),
    [job]
  );

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold">Intercambio de datos (Excel/CSV)</h1>

      <section className="border rounded p-4 space-y-3 bg-white">
        <h2 className="font-semibold">Wizard de importación</h2>
        <input multiple type="file" accept=".xlsx,.xlsm,.csv,.xls,.ods" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
        <div className="flex gap-2">
          <button className="px-3 py-2 bg-blue-600 text-white rounded" disabled={!files.length || loading} onClick={doAnalyze}>Analizar (dry-run)</button>
          <button className="px-3 py-2 bg-green-600 text-white rounded" disabled={!job?.id} onClick={doExecute}>Ejecutar importación</button>
        </div>
        {job && (
          <div className="text-sm">
            <p>Job: #{job.id} - estado: {job.estado}</p>
            <p>Advertencias de ambigüedad: {totalWarnings}</p>
            <div className="overflow-auto max-h-72 border mt-2">
              <table className="min-w-full text-xs">
                <thead><tr><th>Archivo</th><th>Hoja</th><th>Entidad</th><th>Confianza</th><th>Filas</th></tr></thead>
                <tbody>
                  {(job.files || []).flatMap((f: any) => (f.sheets || []).map((s: any) => (
                    <tr key={`${f.id}-${s.id}`}>
                      <td>{f.nombre}</td><td>{s.sheet_name}</td><td>{s.entidad_detectada}</td><td>{s.confianza}</td><td>{s.resumen?.rows}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section className="border rounded p-4 bg-white">
        <h2 className="font-semibold">Historial básico de importaciones</h2>
        <ul className="list-disc pl-5 text-sm">
          {imports.map((i) => <li key={i.id}>Job #{i.id} - {i.estado} - {new Date(i.created_at).toLocaleString()}</li>)}
        </ul>
      </section>

      <section className="border rounded p-4 bg-white">
        <h2 className="font-semibold">Plantillas disponibles</h2>
        <div className="flex flex-wrap gap-2 mt-2">
          {plantillas.map((p) => (
            <a key={p.codigo} href={intercambioApi.descargarPlantillaUrl(p.codigo)} className="px-2 py-1 rounded border text-sm" target="_blank" rel="noreferrer">
              Descargar {p.codigo}
            </a>
          ))}
        </div>
      </section>

      <section className="border rounded p-4 bg-white space-y-2">
        <h2 className="font-semibold">Exportación</h2>
        <div className="flex gap-2 flex-wrap">
          {profiles.map((p) => (
            <button key={p.codigo} className="px-3 py-2 border rounded" onClick={async () => setExportJob(await intercambioApi.generarExportacion(p.codigo))}>
              Generar {p.nombre}
            </button>
          ))}
        </div>
        {exportJob && <a className="text-blue-700 underline" href={intercambioApi.descargarExportacionUrl(exportJob.id)}>Descargar exportación #{exportJob.id}</a>}
      </section>
    </div>
  );
}
