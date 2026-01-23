import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Layout from './components/Layout';
import Configuracion from './pages/Configuracion';
import MiPerfil from './pages/MiPerfil';
import Listados from './pages/Listados';
import Articulos from './pages/Articulos';
import Taller from './pages/Taller';
import Ventas from './pages/Ventas';
import CuentasDia from './pages/CuentasDia';
import DetallesCuentas from './pages/DetallesCuentas';
import Facturas from './pages/Facturas';
import Remisiones from './pages/Remisiones';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="configuracion" element={<Configuracion />} />
            <Route path="mi-perfil" element={<MiPerfil />} />
            <Route path="listados" element={<Listados />} />
            <Route path="articulos" element={<Articulos />} />
            <Route path="taller" element={<Taller />} />
            <Route path="ventas" element={<Ventas />} />
            <Route path="ventas/cuentas-dia" element={<CuentasDia />} />
            <Route path="ventas/detalles-cuentas" element={<DetallesCuentas />} />
            <Route path="facturacion/facturas" element={<Facturas />} />
            <Route path="facturacion/remisiones" element={<Remisiones />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
