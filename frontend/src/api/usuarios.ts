export interface DescuentoApprovalPayload {
  username: string;
  password: string;
  descuento_porcentaje: number;
}

export interface DescuentoApprovalResponse {
  id: number;
  nombre: string;
  descuento_maximo?: string | null;
}

const API_URL = '/api';

export const usuariosApi = {
  async validarDescuento(payload: DescuentoApprovalPayload): Promise<DescuentoApprovalResponse> {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/usuarios/validar_descuento/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'No se pudo validar el descuento');
    }

    return response.json();
  },
};
