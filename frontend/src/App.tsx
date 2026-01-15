import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Layout from './components/Layout';
import Configuracion from './pages/Configuracion';
import Listados from './pages/Listados';
import Articulos from './pages/Articulos';
import Taller from './pages/Taller';
import Ventas from './pages/Ventas';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="configuracion" element={<Configuracion />} />
            <Route path="listados" element={<Listados />} />
            <Route path="articulos" element={<Articulos />} />
            <Route path="taller" element={<Taller />} />
            <Route path="ventas" element={<Ventas />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
