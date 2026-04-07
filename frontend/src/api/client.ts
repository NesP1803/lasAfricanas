import axios from 'axios';
import type { AxiosRequestConfig, Method, ResponseType } from 'axios';

const API_ORIGIN = import.meta.env.VITE_API_URL?.replace(/\/$/, '') || '';
const API_BASE_URL = API_ORIGIN ? `${API_ORIGIN}/api` : '/api';

const toApiUrl = (path: string) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

// Configuración base de Axios
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const LEGACY_ACCESS_TOKEN_KEY = 'token';

const clearAuthStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
};

const getAccessToken = () => localStorage.getItem(ACCESS_TOKEN_KEY);
const getRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY);
let refreshPromise: Promise<string> | null = null;

const setAccessToken = (accessToken: string) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY);
};

const setRefreshToken = (refreshToken: string) => {
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
};

const setAuthTokens = ({ accessToken, refreshToken }: { accessToken: string; refreshToken?: string }) => {
  setAccessToken(accessToken);
  if (refreshToken) {
    setRefreshToken(refreshToken);
  }
};

const decodeJwtExp = (token: string): number | null => {
  try {
    const payloadBase64 = token.split('.')[1];
    if (!payloadBase64) {
      return null;
    }
    const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/');
    const json = JSON.parse(window.atob(base64)) as { exp?: number };
    return typeof json.exp === 'number' ? json.exp : null;
  } catch {
    return null;
  }
};

const isTokenExpired = (token: string, skewSeconds = 15): boolean => {
  const exp = decodeJwtExp(token);
  if (!exp) {
    return false;
  }
  const now = Math.floor(Date.now() / 1000);
  return exp <= now + skewSeconds;
};

const refreshAccessToken = async (): Promise<string> => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token');
  }
  const response = await axios.post(toApiUrl('/auth/refresh/'), {
    refresh: refreshToken,
  });
  const { access } = response.data as { access: string };
  if (!access) {
    throw new Error('Refresh inválido: sin access token');
  }
  setAuthTokens({ accessToken: access });
  return access;
};

const ensureValidAccessToken = async (): Promise<string | null> => {
  const currentToken = getAccessToken();
  if (!currentToken) {
    return null;
  }
  if (!isTokenExpired(currentToken)) {
    return currentToken;
  }

  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
};

// Interceptor para agregar token JWT en cada request
apiClient.interceptors.request.use(
  async (config) => {
    const url = String(config.url || '');
    if (url.includes('/auth/login/') || url.includes('/auth/refresh/')) {
      return config;
    }
    const token = await ensureValidAccessToken();
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
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null;
          });
        }
        const access = await refreshPromise;

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

export {
  API_BASE_URL,
  toApiUrl,
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  clearAuthStorage,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
  setAuthTokens,
};
export default apiClient;
