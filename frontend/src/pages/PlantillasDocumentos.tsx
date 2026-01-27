import { useEffect, useMemo, useState } from "react";
import { Plus, Copy, CheckCircle2, Eye, Save } from "lucide-react";
import { templatesApi } from "../api/templates";
import { useAuth } from "../contexts/AuthContext";
import { useNotification } from "../contexts/NotificationContext";
import type { DocumentType, OutputType, Template, TemplateVersion } from "../types";

const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
  { value: "QUOTATION", label: "Cotización" },
  { value: "INVOICE", label: "Factura de venta" },
  { value: "DELIVERY_NOTE", label: "Remisión" },
  { value: "CREDIT_NOTE", label: "Nota crédito" },
  { value: "DEBIT_NOTE", label: "Nota débito" },
];

const OUTPUT_TYPES: { value: OutputType; label: string }[] = [
  { value: "PDF", label: "PDF" },
  { value: "RECEIPT", label: "Tirilla" },
];

const VARIABLE_GROUPS = [
  {
    title: "Empresa",
    tokens: ["empresa.nombre", "empresa.nit", "empresa.direccion", "empresa.ciudad", "empresa.telefono"],
  },
  {
    title: "Documento",
    tokens: ["doc.tipo", "doc.numero", "doc.fecha", "doc.hora", "doc.estado", "doc.medio_pago", "doc.observaciones"],
  },
  {
    title: "Cliente",
    tokens: ["cliente.nombre", "cliente.nit", "cliente.direccion", "cliente.telefono"],
  },
  {
    title: "Items",
    tokens: [
      "items[].descripcion",
      "items[].codigo",
      "items[].cantidad",
      "items[].valor_unitario",
      "items[].descuento",
      "items[].iva_pct",
      "items[].total",
    ],
  },
  {
    title: "Totales",
    tokens: ["totales.subtotal", "totales.impuestos", "totales.descuentos", "totales.total", "totales.recibido", "totales.cambio"],
  },
];

const DEFAULT_HTML = "<h1>Plantilla nueva</h1>";
const DEFAULT_CSS = "body { font-family: Arial, sans-serif; }";
const DEFAULT_RECEIPT = "[CENTER]Plantilla nueva\n[LINE]";

export default function PlantillasDocumentos() {
  const { user } = useAuth();
  const { showNotification } = useNotification();
  const isAdmin = user?.role?.toUpperCase() === "ADMIN";

  const [documentType, setDocumentType] = useState<DocumentType>("INVOICE");
  const [outputType, setOutputType] = useState<OutputType>("PDF");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [html, setHtml] = useState(DEFAULT_HTML);
  const [css, setCss] = useState(DEFAULT_CSS);
  const [receiptText, setReceiptText] = useState(DEFAULT_RECEIPT);
  const [comment, setComment] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewReceipt, setPreviewReceipt] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState("");
  const [versionModal, setVersionModal] = useState<TemplateVersion | null>(null);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await templatesApi.listTemplates({
        document_type: documentType,
        output_type: outputType,
      });
      setTemplates(data);
      if (!selectedTemplate || !data.find((tpl) => tpl.id === selectedTemplate.id)) {
        setSelectedTemplate(data[0] ?? null);
      }
    } catch (error) {
      console.error(error);
      showNotification({ message: "Error cargando plantillas", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const loadVersions = async (templateId: number) => {
    try {
      const data = await templatesApi.listVersions(templateId);
      setVersions(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, [documentType, outputType]);

  useEffect(() => {
    if (!selectedTemplate) {
      return;
    }
    const current = selectedTemplate.current_version;
    if (selectedTemplate.output_type === "PDF") {
      setHtml(current?.html ?? DEFAULT_HTML);
      setCss(current?.css ?? DEFAULT_CSS);
    } else {
      setReceiptText(current?.receipt_text ?? DEFAULT_RECEIPT);
    }
    loadVersions(selectedTemplate.id);
  }, [selectedTemplate]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleCreateTemplate = async () => {
    if (!newTemplateName.trim()) {
      showNotification({ message: "Debes ingresar un nombre.", type: "info" });
      return;
    }
    try {
      const template = await templatesApi.createTemplate({
        name: newTemplateName,
        document_type: documentType,
        output_type: outputType,
        html: outputType === "PDF" ? html : undefined,
        css: outputType === "PDF" ? css : undefined,
        receipt_text: outputType === "RECEIPT" ? receiptText : undefined,
        comment: "Creación inicial",
      });
      setTemplates((prev) => [...prev, template]);
      setSelectedTemplate(template);
      setModalOpen(false);
      setNewTemplateName("");
      showNotification({ message: "Plantilla creada.", type: "success" });
    } catch (error) {
      console.error(error);
      showNotification({ message: "Error creando plantilla.", type: "error" });
    }
  };

  const handleDuplicate = async () => {
    if (!selectedTemplate) return;
    try {
      const template = await templatesApi.duplicateTemplate(selectedTemplate.id);
      setTemplates((prev) => [...prev, template]);
      showNotification({ message: "Plantilla duplicada.", type: "success" });
    } catch (error) {
      console.error(error);
      showNotification({ message: "Error duplicando plantilla.", type: "error" });
    }
  };

  const handleActivate = async () => {
    if (!selectedTemplate) return;
    try {
      await templatesApi.activateTemplate(selectedTemplate.id);
      showNotification({ message: "Plantilla activada.", type: "success" });
      await loadTemplates();
    } catch (error) {
      console.error(error);
      showNotification({ message: "No se pudo activar.", type: "error" });
    }
  };

  const handleSaveVersion = async () => {
    if (!selectedTemplate) return;
    try {
      const payload =
        outputType === "PDF"
          ? { html, css, comment }
          : { receipt_text: receiptText, comment };
      await templatesApi.createVersion(selectedTemplate.id, payload);
      showNotification({ message: "Versión guardada.", type: "success" });
      setComment("");
      await loadTemplates();
      await loadVersions(selectedTemplate.id);
    } catch (error) {
      console.error(error);
      showNotification({ message: "Error guardando versión.", type: "error" });
    }
  };

  const handlePreview = async () => {
    if (!selectedTemplate) return;
    try {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setPreviewReceipt([]);
      const result = await templatesApi.previewTemplate({
        document_type: documentType,
        output_type: outputType,
        template_version_id: selectedTemplate.current_version?.id,
      });
      if (outputType === "PDF") {
        const blob = new Blob([result as ArrayBuffer], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      } else {
        const data = result as { rendered_lines?: string[] };
        setPreviewReceipt(data.rendered_lines ?? []);
      }
    } catch (error) {
      console.error(error);
      showNotification({
        message: "No se pudo generar la vista previa.",
        type: "error",
      });
    }
  };

  const handleRestoreVersion = async (versionId: number) => {
    if (!selectedTemplate) return;
    try {
      await templatesApi.restoreVersion(selectedTemplate.id, versionId);
      showNotification({ message: "Versión restaurada.", type: "success" });
      await loadTemplates();
      await loadVersions(selectedTemplate.id);
    } catch (error) {
      console.error(error);
      showNotification({ message: "Error restaurando versión.", type: "error" });
    }
  };

  const activeTemplates = useMemo(
    () => templates.filter((tpl) => tpl.is_active),
    [templates]
  );

  if (!isAdmin) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold text-slate-800">Plantillas de documentos</h1>
        <p className="mt-2 text-slate-600">No tienes permisos para acceder a este módulo.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">
            Plantillas de documentos
          </h1>
          <p className="text-slate-500 text-sm">
            Administra las versiones PDF y tirilla con vista previa en tiempo real.
          </p>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-white"
          onClick={() => setModalOpen(true)}
        >
          <Plus size={18} /> Crear plantilla
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-600">Tipo de documento</label>
            <select
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value as DocumentType)}
            >
              {DOCUMENT_TYPES.map((doc) => (
                <option key={doc.value} value={doc.value}>
                  {doc.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-600">Salida</label>
            <select
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
              value={outputType}
              onChange={(event) => setOutputType(event.target.value as OutputType)}
            >
              {OUTPUT_TYPES.map((output) => (
                <option key={output.value} value={output.value}>
                  {output.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium text-slate-600">Plantillas</div>
            <div className="space-y-2 max-h-[320px] overflow-auto">
              {loading && <p className="text-xs text-slate-400">Cargando...</p>}
              {!loading && templates.length === 0 && (
                <p className="text-xs text-slate-400">No hay plantillas.</p>
              )}
              {templates.map((tpl) => (
                <button
                  key={tpl.id}
                  onClick={() => setSelectedTemplate(tpl)}
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    selectedTemplate?.id === tpl.id
                      ? "border-blue-500 bg-blue-50"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-700">{tpl.name}</span>
                    {tpl.is_active && (
                      <CheckCircle2 size={14} className="text-green-500" />
                    )}
                  </div>
                  <p className="text-xs text-slate-500">Versión {tpl.current_version?.version_number ?? "-"}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <button
              className="flex w-full items-center justify-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={handleDuplicate}
              disabled={!selectedTemplate}
            >
              <Copy size={16} /> Duplicar
            </button>
            <button
              className="flex w-full items-center justify-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 hover:bg-green-100"
              onClick={handleActivate}
              disabled={!selectedTemplate}
            >
              <CheckCircle2 size={16} /> Activar
            </button>
          </div>

          <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-500">
            Activas: {activeTemplates.length}
          </div>
        </div>

        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[1fr_260px]">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-800">Editor</h2>
                <div className="flex gap-2">
                  <button
                    className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                    onClick={handlePreview}
                  >
                    <Eye size={16} /> Vista previa
                  </button>
                  <button
                    className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
                    onClick={handleSaveVersion}
                  >
                    <Save size={16} /> Guardar nueva versión
                  </button>
                </div>
              </div>

              {outputType === "PDF" ? (
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-slate-600">HTML</label>
                    <textarea
                      className="mt-2 h-64 w-full rounded-md border border-slate-200 p-3 font-mono text-xs"
                      value={html}
                      onChange={(event) => setHtml(event.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-600">CSS</label>
                    <textarea
                      className="mt-2 h-40 w-full rounded-md border border-slate-200 p-3 font-mono text-xs"
                      value={css}
                      onChange={(event) => setCss(event.target.value)}
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-sm font-medium text-slate-600">Tirilla</label>
                  <textarea
                    className="mt-2 h-64 w-full rounded-md border border-slate-200 p-3 font-mono text-xs"
                    value={receiptText}
                    onChange={(event) => setReceiptText(event.target.value)}
                  />
                  <p className="mt-2 text-xs text-slate-400">
                    Etiquetas disponibles: [CENTER], [RIGHT], [LEFT], [B], [/B], [LINE], [CUT]
                  </p>
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-slate-600">Comentario</label>
                <input
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="Describe los cambios de esta versión"
                />
              </div>

              {outputType === "PDF" && previewUrl && (
                <iframe
                  title="Vista previa PDF"
                  src={previewUrl}
                  className="h-80 w-full rounded-md border border-slate-200"
                />
              )}
              {outputType === "RECEIPT" && previewReceipt.length > 0 && (
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap">
                  {previewReceipt.join("\n")}
                </div>
              )}
            </div>

            <aside className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm space-y-4">
              <h3 className="text-sm font-semibold text-slate-700">
                Variables disponibles
              </h3>
              {VARIABLE_GROUPS.map((group) => (
                <div key={group.title} className="space-y-1">
                  <p className="text-xs font-semibold text-slate-500 uppercase">
                    {group.title}
                  </p>
                  <ul className="space-y-1 text-xs text-slate-600">
                    {group.tokens.map((token) => (
                      <li key={token}>
                        <code>{"{{ " + token + " }}"}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <div className="text-xs text-slate-500">
                <p>Loops:</p>
                <code>{`{% for item in items %}...{% endfor %}`}</code>
              </div>
            </aside>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-800 mb-4">Historial de versiones</h2>
            <div className="overflow-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="py-2 pr-4">Versión</th>
                    <th className="py-2 pr-4">Fecha</th>
                    <th className="py-2 pr-4">Usuario</th>
                    <th className="py-2 pr-4">Comentario</th>
                    <th className="py-2 pr-4">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((version) => (
                    <tr key={version.id} className="border-b border-slate-100">
                      <td className="py-2 pr-4">v{version.version_number}</td>
                      <td className="py-2 pr-4">
                        {new Date(version.created_at).toLocaleString()}
                      </td>
                      <td className="py-2 pr-4">{version.created_by_name ?? "Sistema"}</td>
                      <td className="py-2 pr-4">{version.comment}</td>
                      <td className="py-2 pr-4 flex gap-2">
                        <button
                          className="text-blue-600 hover:underline"
                          onClick={() => setVersionModal(version)}
                        >
                          Ver
                        </button>
                        <button
                          className="text-green-600 hover:underline"
                          onClick={() => handleRestoreVersion(version.id)}
                        >
                          Restaurar
                        </button>
                      </td>
                    </tr>
                  ))}
                  {versions.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-slate-400">
                        Sin versiones registradas.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 space-y-4">
            <h2 className="text-lg font-semibold text-slate-800">Nueva plantilla</h2>
            <div>
              <label className="text-sm font-medium text-slate-600">Nombre</label>
              <input
                className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2"
                value={newTemplateName}
                onChange={(event) => setNewTemplateName(event.target.value)}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                className="rounded-md border border-slate-200 px-4 py-2 text-sm"
                onClick={() => setModalOpen(false)}
              >
                Cancelar
              </button>
              <button
                className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white"
                onClick={handleCreateTemplate}
              >
                Crear
              </button>
            </div>
          </div>
        </div>
      )}

      {versionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-2xl rounded-lg bg-white p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-800">
                Versión v{versionModal.version_number}
              </h2>
              <button
                className="text-sm text-slate-500 hover:underline"
                onClick={() => setVersionModal(null)}
              >
                Cerrar
              </button>
            </div>
            {selectedTemplate?.output_type === "PDF" ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold text-slate-500">HTML</p>
                  <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-slate-50 p-3 text-xs">
                    {versionModal.html}
                  </pre>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-500">CSS</p>
                  <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-slate-50 p-3 text-xs">
                    {versionModal.css}
                  </pre>
                </div>
              </div>
            ) : (
              <div>
                <p className="text-xs font-semibold text-slate-500">Tirilla</p>
                <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-slate-50 p-3 text-xs">
                  {versionModal.receipt_text}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
