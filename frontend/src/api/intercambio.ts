import apiClient from './client';

export const intercambioApi = {
  analizar: async (files: File[], profileId?: number) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    if (profileId) formData.append('profile_id', String(profileId));
    const response = await apiClient.post('/intercambio/importaciones/analizar/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  ejecutar: async (jobId: number) => {
    const response = await apiClient.post('/intercambio/importaciones/ejecutar/', { job_id: jobId });
    return response.data;
  },
  listarImportaciones: async () => (await apiClient.get('/intercambio/importaciones/')).data,
  obtenerErrores: async (id: number) => (await apiClient.get(`/intercambio/importaciones/${id}/errores/`)).data,
  listarPlantillas: async () => (await apiClient.get('/intercambio/plantillas/')).data,
  descargarPlantillaUrl: (codigo: string) => `/api/intercambio/plantillas/${codigo}/descargar/`,
  perfilesExportacion: async () => (await apiClient.get('/intercambio/exportaciones/perfiles/')).data,
  generarExportacion: async (profileCode: string) => (await apiClient.post('/intercambio/exportaciones/generar/', { profile_code: profileCode })).data,
  descargarExportacionUrl: (id: number) => `/api/intercambio/exportaciones/${id}/descargar/`,
};
