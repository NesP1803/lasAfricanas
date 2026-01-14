import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import PuntoVenta from './pages/PuntoVenta';
import Taller from './pages/Taller';
import TallerNuevoServicio from './pages/TallerNuevoServicio';
import TallerDetalle from './pages/TallerDetalle';
import TallerHistorial from './pages/TallerHistorial';
import Layout from './components/Layout';
import Configuracion from './pages/Configuracion';
import Listados from './pages/Listados';
import Articulos from './pages/Articulos';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="ventas" element={<PuntoVenta />} />
            <Route path="taller" element={<Taller />} />
            <Route path="taller/nuevo" element={<TallerNuevoServicio />} />
            <Route path="taller/:id" element={<TallerDetalle />} />
            <Route path="taller/historial/:placa" element={<TallerHistorial />} />
            <Route path="configuracion" element={<Configuracion />} />
            <Route path="listados" element={<Listados />} />
            <Route path="articulos" element={<Articulos />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
