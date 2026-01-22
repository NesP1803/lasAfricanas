import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { configuracionAPI } from '../api/configuracion';
import type { ModulosPermitidos } from '../types';

interface User {
  id: number;
  username: string;
  role: string;
  email?: string;
  modulos_permitidos?: ModulosPermitidos | null;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    if (token && savedUser) {
      try {
        return JSON.parse(savedUser) as User;
      } catch (error) {
        console.error('Error parsing saved user:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
    return null;
  });

  const persistUser = (nextUser: User | null) => {
    if (!nextUser) {
      localStorage.removeItem('user');
      setUser(null);
      return;
    }
    localStorage.setItem('user', JSON.stringify(nextUser));
    setUser(nextUser);
  };

  const login = async (username: string, password: string) => {
    try {
      console.log('Intentando login con:', { username });
      
      const response = await fetch('/api/auth/login/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      console.log('Response status:', response.status);

      const parseResponseBody = async () => {
        const text = await response.text();
        if (!text) {
          return null;
        }
        try {
          return JSON.parse(text);
        } catch (parseError) {
          console.error('Error parsing login response:', parseError);
          throw new Error('Respuesta inválida del servidor');
        }
      };

      if (!response.ok) {
        const errorData = await parseResponseBody();
        const message =
          errorData?.detail ||
          errorData?.error ||
          `Error ${response.status}: ${response.statusText}`;
        throw new Error(message || 'Usuario o contraseña incorrectos');
      }

      // Parsear la respuesta JSON directamente
      const data = await parseResponseBody();
      if (!data) {
        throw new Error('Respuesta del servidor vacía');
      }
      console.log('Login exitoso:', data);
      
      // Verificar que tengamos los datos del usuario
      if (!data.user) {
        throw new Error('Respuesta del servidor sin datos de usuario');
      }
      
      // Guardar el token y datos del usuario
      localStorage.setItem('token', data.access);
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      persistUser({
        id: data.user.id,
        username: data.user.username,
        role: data.user.role,
        email: data.user.email,
        modulos_permitidos: data.user.modulos_permitidos ?? null,
      });
    } catch (error) {
      console.error('Error completo en login:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    persistUser(null);
  };

  useEffect(() => {
    if (!user) {
      return;
    }

    let isMounted = true;

    const refreshUser = async () => {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      if (!token) {
        return;
      }
      try {
        const data = await configuracionAPI.obtenerUsuarioActual();
        if (!isMounted) {
          return;
        }
        const updatedUser: User = {
          id: data.id,
          username: data.username,
          role: data.tipo_usuario ?? user.role,
          email: data.email,
          modulos_permitidos: data.modulos_permitidos ?? user.modulos_permitidos ?? null,
        };
        persistUser(updatedUser);
      } catch (error) {
        console.error('Error actualizando usuario actual:', error);
      }
    };

    refreshUser();
    const intervalId = window.setInterval(refreshUser, 60000);
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshUser();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [user]);

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
