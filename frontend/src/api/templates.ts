import apiClient from "./client";
import type { DocumentType, OutputType, Template, TemplateVersion } from "../types";

export type TemplateCreatePayload = {
  name: string;
  document_type: DocumentType;
  output_type: OutputType;
  is_active?: boolean;
  html?: string | null;
  css?: string | null;
  receipt_text?: string | null;
  comment?: string;
};

export type TemplateVersionPayload = {
  html?: string | null;
  css?: string | null;
  receipt_text?: string | null;
  comment?: string;
};

export type TemplatePreviewPayload = {
  document_type: DocumentType;
  output_type: OutputType;
  template_version_id?: number;
  document_id?: number;
};

export const templatesApi = {
  async listTemplates(params?: {
    document_type?: DocumentType;
    output_type?: OutputType;
  }): Promise<Template[]> {
    const response = await apiClient.get("/templates/", { params });
    return response.data;
  },

  async createTemplate(payload: TemplateCreatePayload): Promise<Template> {
    const response = await apiClient.post("/templates/", payload);
    return response.data;
  },

  async duplicateTemplate(id: number): Promise<Template> {
    const response = await apiClient.post(`/templates/${id}/duplicate/`);
    return response.data;
  },

  async activateTemplate(id: number): Promise<void> {
    await apiClient.patch(`/templates/${id}/activate/`);
  },

  async listVersions(id: number): Promise<TemplateVersion[]> {
    const response = await apiClient.get(`/templates/${id}/versions/`);
    return response.data;
  },

  async createVersion(
    id: number,
    payload: TemplateVersionPayload
  ): Promise<TemplateVersion> {
    const response = await apiClient.post(`/templates/${id}/versions/`, payload);
    return response.data;
  },

  async restoreVersion(id: number, versionId: number): Promise<void> {
    await apiClient.post(`/templates/${id}/restore_version/`, {
      version_id: versionId,
    });
  },

  async previewTemplate(
    payload: TemplatePreviewPayload
  ): Promise<ArrayBuffer | { rendered_lines?: string[]; template: string }> {
    if (payload.output_type === "PDF") {
      const response = await apiClient.post("/templates/preview/", payload, {
        responseType: "arraybuffer",
      });
      return response.data;
    }
    const response = await apiClient.post("/templates/preview/", payload);
    return response.data;
  },

  async fetchDocumentPdf(
    docType: DocumentType,
    documentId: number,
    templateVersionId?: number
  ): Promise<ArrayBuffer> {
    const response = await apiClient.get(
      `/documents/${docType}/${documentId}/pdf/`,
      {
        params: templateVersionId ? { template_version_id: templateVersionId } : {},
        responseType: "arraybuffer",
      }
    );
    return response.data;
  },

  async fetchDocumentReceipt(
    docType: DocumentType,
    documentId: number,
    templateVersionId?: number
  ): Promise<{ template: string; context: unknown; rendered_lines: string[] }> {
    const response = await apiClient.get(
      `/documents/${docType}/${documentId}/receipt/`,
      {
        params: templateVersionId ? { template_version_id: templateVersionId } : {},
      }
    );
    return response.data;
  },
};
