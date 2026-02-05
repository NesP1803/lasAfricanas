import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  
  const { login } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const storedLogo = localStorage.getItem('empresa_logo');
    if (storedLogo) {
      setLogoUrl(storedLogo);
      return;
    }

    const cargarLogo = async () => {
      try {
        const response = await fetch('/api/configuracion-empresa/');
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        const logo = data?.[0]?.logo ?? null;
        if (logo) {
          setLogoUrl(logo);
          localStorage.setItem('empresa_logo', logo);
        }
      } catch (error) {
        console.error('Error cargando logo:', error);
      }
    };

    cargarLogo();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!username || !password) {
      setError('Por favor ingrese usuario y contraseña');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await login(username, password);
      navigate('/');
    } catch (error: any) {
      console.error('Error login:', error);
      setError(error.message || 'Usuario o contraseña incorrectos');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-md p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          {logoUrl ? (
            <div className="w-32 h-32 mx-auto mb-4 rounded-full overflow-hidden bg-blue-100">
              <img
                src={logoUrl}
                alt="Logo de la empresa"
                className="h-full w-full object-cover"
              />
            </div>
          ) : (
            <div className="w-32 h-32 mx-auto mb-4 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center">
              <span className="text-white text-4xl font-bold">LA</span>
            </div>
          )}
          <h1 className="text-3xl font-bold text-gray-800">Las Africanas</h1>
          <p className="text-gray-600">Sistema de Gestión</p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            <p className="text-sm font-semibold">{error}</p>
          </div>
        )}

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Usuario
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Ingrese su usuario"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Contraseña
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Ingrese su contraseña"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
          </button>
        </form>

      </div>
    </div>
  );
}
