import axios from 'axios';
import type { AxiosRequestConfig, Method, ResponseType } from 'axios';

// Configuración base de Axios
const apiClient = axios.create({
  baseURL: '/api', // Vite proxy redirigirá a http://127.0.0.1:8000/api
  headers: {
    'Content-Type': 'application/json',
  },
});

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const LEGACY_TOKEN_KEY = 'token';

const clearAuthStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
};

const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_KEY);

const setAccessToken = (accessToken: string) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
};

// Interceptor para agregar token JWT en cada request
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor para manejar errores de autenticación
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const requestUrl: string = originalRequest?.url || '';

    // Si el error es 401 y no es login/refresh, intentar refresh
    if (
      error.response?.status === 401 &&
      !originalRequest?._retry &&
      !requestUrl.includes('/auth/login/') &&
      !requestUrl.includes('/auth/refresh/')
    ) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
        if (!refreshToken) {
          throw new Error('No refresh token');
        }

        const response = await axios.post('/api/auth/refresh/', {
          refresh: refreshToken,
        });

        const { access } = response.data;
        setAccessToken(access);

        originalRequest.headers.Authorization = `Bearer ${access}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Si el refresh falla, limpiar tokens y redirigir a login
        clearAuthStorage();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

type AuthFetchOptions = Omit<RequestInit, 'body' | 'method'> & {
  body?: BodyInit | null;
  method?: Method;
  responseType?: ResponseType;
};

export const authFetch = async (input: string, options: AuthFetchOptions = {}) => {
  const {
    method = 'GET',
    body,
    headers,
    signal,
    responseType = 'json',
  } = options;

  const normalizedUrl = input.startsWith('/api') ? input.replace(/^\/api/, '') : input;

  const requestHeaders = Object.fromEntries(
    Object.entries((headers as Record<string, string>) || {}).filter(
      ([key]) => key.toLowerCase() !== 'authorization'
    )
  );

  const config: AxiosRequestConfig = {
    url: normalizedUrl,
    method,
    signal: signal ?? undefined,
    headers: requestHeaders,
    responseType,
    data:
      typeof body === 'string' &&
      ((requestHeaders['Content-Type'] || requestHeaders['content-type'])?.includes('application/json'))
        ? JSON.parse(body)
        : body,
  };

  try {
    const response = await apiClient.request(config);
    return {
      ok: true,
      status: response.status,
      json: async () => response.data,
      blob: async () => response.data,
      text: async () => (typeof response.data === 'string' ? response.data : JSON.stringify(response.data)),
    };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      const errorData = error.response.data;
      return {
        ok: false,
        status: error.response.status,
        json: async () => errorData,
        blob: async () => errorData,
        text: async () => (typeof errorData === 'string' ? errorData : JSON.stringify(errorData)),
      };
    }
    throw error;
  }
};

export { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, LEGACY_TOKEN_KEY, clearAuthStorage, getAccessToken, setAccessToken };
export default apiClient;
