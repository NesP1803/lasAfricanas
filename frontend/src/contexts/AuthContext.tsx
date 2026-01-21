import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { ModuleAccess } from '../store/moduleAccess';

interface User {
  id: number;
  username: string;
  role: string;
  email?: string;
  modulos_permitidos?: ModuleAccess;
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

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Usuario o contraseña incorrectos');
      }

      // Parsear la respuesta JSON directamente
      const data = await response.json();
      console.log('Login exitoso:', data);
      
      // Verificar que tengamos los datos del usuario
      if (!data.user) {
        throw new Error('Respuesta del servidor sin datos de usuario');
      }
      
      // Guardar el token y datos del usuario
      localStorage.setItem('token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      setUser({
        id: data.user.id,
        username: data.user.username,
        role: data.user.role,
        email: data.user.email,
        modulos_permitidos: data.user.modulos_permitidos,
      });
    } catch (error) {
      console.error('Error completo en login:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setUser(null);
  };

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
